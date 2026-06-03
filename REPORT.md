# Technical Report: Backend Management and Server Requirements
## Climate Academy RAG Chatbot : NIPGR Deployment

---

## Section 1: Concurrent User Management

### 1.1 Architectural Overview

The chatbot backend manages concurrent users through a layered asynchronous architecture that decouples HTTP request handling from the computationally expensive RAG pipeline. This separation is the fundamental design decision that allows the system to remain responsive under concurrent load without any single user's request blocking another.

The stack consists of four cooperating processes: Gunicorn running Flask workers, Celery background workers, Redis serving as both message broker and session store, and Ollama serving the language model. Each layer handles concurrency differently and has a different bottleneck characteristic.

### 1.2 HTTP Layer , Gunicorn with Gevent Workers

Gunicorn is configured with four worker processes using the gevent async worker class. Gevent workers use cooperative multitasking , each worker can hold thousands of open HTTP connections simultaneously by yielding the CPU when waiting for I/O, rather than blocking. This means that when a client is polling `/result/<task_id>` and waiting for a response, the Gunicorn worker handling that connection is not occupying a CPU core , it yields and handles other connections in the meantime.

The practical effect is that four Gunicorn workers can comfortably handle the polling requests of 80–100 simultaneous users without resource contention at the HTTP layer. Flask itself is stateless i.e. it holds no per-user state between requests. All state (conversation history, task results) lives in Redis, which means any Gunicorn worker can handle any request from any user interchangeably.

### 1.3 Task Queue , Celery with Redis Broker

When a user sends a message via `POST /chat`, Flask does not execute the RAG pipeline. Instead it creates a Celery task, pushes it onto a Redis queue, and immediately returns a `task_id` to the client. This HTTP round-trip completes in under 50 milliseconds regardless of how busy the system is.

Celery workers independently watch the Redis queue and pick up tasks as they arrive. The system is configured with two Celery workers, each capable of handling one RAG pipeline execution at a time. When both workers are busy and a third request arrives, it sits in the Redis queue and waits. The client continues polling `/result/<task_id>` and receives `{"status": "pending"}` until a worker becomes free. This queuing behaviour means the system never crashes or returns errors under concurrent load — requests are serialised and processed in order.

The consequence of two Celery workers is that at maximum only two full RAG pipelines run simultaneously. For a small-to-medium lab deployment with up to 100 users, this is acceptable because users do not all submit messages at the exact same millisecond. In practice, queue wait times remain short under normal usage patterns.

### 1.4 Session Isolation

Each user session is completely isolated. When a user calls `POST /session`, a UUID is generated and an empty conversation history list is stored in Redis under the key `session:<uuid>` with a 24-hour TTL. Every subsequent message from that user includes their session ID, and the Celery worker handling their task reads only their history from Redis. No user can see or interfere with another user's conversation state. Sessions expire automatically after 24 hours of inactivity without any manual cleanup.

### 1.5 The True Concurrency Bottleneck

The honest bottleneck in this architecture is not the HTTP layer, the task queue, or Redis , it is Ollama. The language model processes one inference request at a time per loaded model instance. If two Celery workers submit generation requests to Ollama simultaneously, one will be queued inside Ollama's internal request queue (configured with `OLLAMA_MAX_QUEUE=512`). The A100 GPU will complete the first inference, then immediately begin the second. There is no error or crash , just sequential processing.

For a deployment where response times of 15–60 seconds per query are already expected, the additional queue wait for concurrent users adds proportional latency that users generally find acceptable for an asynchronous polling interface.

---

## Section 2: Hardware and Resource Allocation

### 2.1 Deployment Context

The application is deployed across two nodes of the NIPGR PhytoCluster HPC facility. The login node (`172.16.41.41`) runs the Flask API, Celery workers, and Redis. The GPU node (`172.16.41.42`, `gpu001`) runs the Ollama LLM inference server. The two nodes communicate over the internal lab network, with the login node calling `http://172.16.41.42:11434` directly.

The GPU node is confirmed to have an **NVIDIA A100 80GB PCIe** GPU, as reported by Ollama at startup:

| inference compute | NVIDIA A100 80GB PCIe | total: 80.0 GiB | available: 78.3 GiB |
|---|---|---|---|


Specific CPU model and RAM capacity of the NIPGR nodes are not known to the authors of this document and are not stated here.

---

### 2.2 GPU Memory Consumption

GPU memory is consumed exclusively by the Ollama process on `gpu001`. No other component of the RAG pipeline uses GPU resources.

**Llama 3.1 8B (4-bit quantized) — approximately 4.9 GB VRAM**

The model file on disk is 4.9 GB as reported by `ollama list`. When loaded into GPU memory, a quantized model occupies approximately the same size as its file representation since 4-bit quantization is already the in-memory format. The A100's 80 GB VRAM holds this model with approximately 75 GB remaining available. This means the model loads entirely into GPU memory with no offloading to system RAM, which is the condition required for fast inference.

**KV Cache — variable, typically 1–4 GB per active inference**

During generation, Ollama maintains a Key-Value attention cache for the current context. The default context length reported at startup is 262,144 tokens (set by Ollama based on available VRAM). In practice, each RAG query uses approximately 2,000–4,000 tokens of context (system prompt with 5 retrieved passages plus conversation history). The KV cache for a single active inference at this context length consumes roughly 1–2 GB. With two Celery workers potentially submitting concurrent requests, peak KV cache usage would be approximately 2–4 GB.

**Total estimated GPU memory consumption: approximately 6–9 GB out of 80 GB available.**

The A100 80GB is substantially over-provisioned for this workload. The same application could run on a GPU with 12–16 GB VRAM, such as an NVIDIA RTX 3080 or A10, without degradation.

---

### 2.3 CPU Memory Consumption (Login Node)

The following components run on the login node CPU and consume system RAM.

**Gunicorn + Flask (4 workers) — approximately 400–600 MB**

Each Gunicorn worker is a full Python process running the Flask application with all imported modules. At approximately 100–150 MB per worker, four workers consume 400–600 MB collectively.

**Celery workers (2 workers) — approximately 1.5–2.5 GB**

Each Celery worker is the most memory-intensive process on the login node because it loads two ML models into CPU RAM.

The MiniLM embedding model (`all-MiniLM-L6-v2`) occupies approximately 90 MB per worker process. Since each Celery worker is an independent process (not threads sharing memory), each worker holds its own copy: approximately 180 MB total across two workers.

This is a proposed improvement ( currently working on dev branch ) :

1.The cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) occupies approximately 80 MB per worker: approximately 160 MB total.

2.The BM25 index is built in-memory from all 1,108 chunks. Each tokenized chunk document averages approximately 150 words. The BM25Okapi structure including inverted index and term frequency matrices for 1,108 documents occupies approximately 50–100 MB per worker.

ChromaDB PersistentClient holds the vector index in memory for fast querying. With 1,108 chunks at 384 dimensions (float32, 4 bytes), the raw vector matrix is approximately 1,108 × 384 × 4 bytes = 1.7 MB. With ChromaDB's internal HNSW index structure and metadata overhead, total memory footprint is approximately 20–50 MB per worker.

**Redis — approximately 50–100 MB**

Redis holds active session histories and Celery task results. With up to 100 concurrent sessions, each storing up to 20 conversation turns at roughly 500 characters per turn, total session data is under 1 MB. Celery task results are stored for one hour before expiry. Total Redis memory footprint is expected to remain well under 100 MB under normal usage.

**Total estimated CPU memory consumption on login node: approximately 2–4 GB.**

---

### 2.4 CPU Compute Consumption

**Embedding (MiniLM) — CPU-bound, approximately 50–200ms per query**

The MiniLM model runs on CPU in this deployment. It is used twice per request: once to embed the user query (at query time inside the Celery worker) and once during ingestion (offline, not at request time). A single embedding call for a 150-word text takes approximately 50–200ms on a modern server CPU. This is the primary CPU-bound operation per request.

This is a proposed improvement ( currently working on dev branch ) :

1. **BM25 scoring — negligible, under 5ms per query**

BM25 scoring over 1,108 documents with a tokenized query is a simple arithmetic operation over sparse vectors. It is effectively instantaneous on any modern CPU.

2. **Cross-encoder reranking — CPU-bound, approximately 200–400ms per query**

The cross-encoder scores 20 `(query, chunk)` pairs sequentially on CPU. This is the second most CPU-intensive operation per request. Each pair requires a forward pass through a 6-layer transformer. Total time for 20 pairs is approximately 200–400ms on a modern server CPU.

**Total CPU compute per user request (excluding Ollama): approximately 300–600ms.**

This is comfortably within the Celery async model since the user is already waiting for Ollama, which takes 15–60 seconds.

---

### 2.5 Impact of CPU-Only vs CPU+GPU Deployment

This is the most practically important comparison for understanding the hardware requirement.

**CPU + GPU (current deployment)**

Ollama loads Llama 3.1 8B entirely into the A100's VRAM. Every transformer layer executes on GPU with the full memory bandwidth of the A100 (approximately 2 TB/s). Token generation speed is approximately 40–80 tokens per second. A typical 300-token response is generated in approximately 4–8 seconds. Total user-perceived latency per request is approximately 10–20 seconds including embedding, retrieval, reranking, and generation.

**CPU-only deployment (hypothetical)**

If Ollama were forced to run entirely on CPU with no GPU, the model would load into system RAM. Llama 3.1 8B quantized requires approximately 5 GB of RAM, which is available on any modern server. However, CPU memory bandwidth is approximately 50–100 GB/s — roughly 20–40 times slower than the A100. Token generation speed on CPU drops to approximately 2–5 tokens per second. A typical 300-token response would take approximately 60–150 seconds to generate. Total user-perceived latency per request would be approximately 70–160 seconds.

**Summary of the difference:**

| Metric | CPU + GPU (A100) | CPU only |
|---|---|---|
| Token generation speed | 40–80 tokens/sec | 2–5 tokens/sec |
| Response generation time | 4–8 seconds | 60–150 seconds |
| Total request latency | 10–20 seconds | 70–160 seconds |
| Practical usability | Acceptable for interactive use | Marginal — frustrating for users |
| Memory requirement | 5 GB VRAM + 2–4 GB RAM | 5 GB RAM (model) + 2–4 GB RAM |

The GPU is not strictly required for the application to function — it will run on CPU only. However, the user experience degrades to the point where interactive conversation becomes impractical. The GPU is therefore a strong practical requirement for a deployment intended for regular use, even though it is not a hard technical dependency.

All components other than Ollama — Flask, Celery, Redis, MiniLM embedding, BM25, ChromaDB, and the cross-encoder reranker — run entirely on CPU and have no GPU dependency. These components collectively consume approximately 2–4 GB of system RAM and approximately 300–600ms of CPU time per request, regardless of whether a GPU is present.

---
### Rate Limiting and Ollama Access Control

**1. Current Configuration**
Currently, our deployment includes a baseline rate-limiting mechanism at the Nginx reverse-proxy level, but it is not specific to Ollama access.

* The `nginx.conf` tracks requests per IP address using a shared memory zone.
* It restricts overall traffic to 20 requests per minute with a burst allowance of 10 requests.
* Because this limit is applied globally to the main server block, it affects all endpoints, including frontend assets, health checks, and result polling.
* There is currently no isolated per-user rate limit restricting the number of generation requests sent specifically to the Ollama model.

**2. Proposed Implementation for Ollama**
To effectively implement a per-user rate limit specifically for Ollama, the best approach is to utilize our existing Redis infrastructure.

* We will implement a sliding window counter at the application layer within Flask keyed by the user's session ID.
* Before dispatching a generation task to the Celery queue via the `/chat` endpoint, the system will execute an atomic increment operation in Redis.
* If a user exceeds the configured threshold (e.g., 10 requests per 60-second window), the backend will block the request and return an HTTP 429 status code.
* This approach guarantees that a single aggressive session cannot overload the Ollama internal queue, while ensuring standard UI interactions and result polling remain unaffected.

---