# app/routes.py
from flask import Blueprint, request, jsonify
from app.session import create_session, delete_session, session_exists
from app.tasks import process_chat
from app.logger import get_logger

logger = get_logger(__name__)

bp = Blueprint("api", __name__)

MAX_MESSAGE_LENGTH = 2000  # characters


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/session", methods=["POST"])
def new_session():
    try:
        session_id = create_session()
        logger.info(f"New session created: {session_id}")
        return jsonify({"session_id": session_id}), 201
    except RuntimeError as e:
        logger.error(f"Session creation failed: {e}")
        return jsonify({"error": "service_unavailable", "message": str(e)}), 503


@bp.route("/session/<session_id>", methods=["DELETE"])
def end_session(session_id):
    try:
        if not session_exists(session_id):
            logger.warning(f"DELETE requested for non-existent session: {session_id}")
            return jsonify({"error": "not_found", "message": "Session not found"}), 404
        delete_session(session_id)
        return jsonify({"message": "Session cleared"}), 200
    except RuntimeError as e:
        logger.error(f"Session deletion failed for {session_id}: {e}")
        return jsonify({"error": "service_unavailable", "message": str(e)}), 503


@bp.route("/chat", methods=["POST"])
def chat():
    # Validate Content-Type
    if not request.is_json:
        logger.warning("Chat request received with non-JSON content type")
        return jsonify({"error": "invalid_content_type", "message": "Content-Type must be application/json"}), 415

    data = request.get_json(silent=True)
    if not data:
        logger.warning("Chat request received with unparseable JSON body")
        return jsonify({"error": "invalid_body", "message": "Request body must be valid JSON"}), 400

    session_id   = data.get("session_id", "").strip()
    user_message = data.get("message",    "").strip()

    # Validate session_id
    if not session_id:
        return jsonify({"error": "missing_field", "message": "session_id is required"}), 400

    # Validate message
    if not user_message:
        return jsonify({"error": "missing_field", "message": "message cannot be empty"}), 400

    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({
            "error": "message_too_long",
            "message": f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters"
        }), 400

    # Validate session exists
    try:
        if not session_exists(session_id):
            logger.warning(f"Chat attempted with invalid session: {session_id}")
            return jsonify({"error": "invalid_session", "message": "Session not found or expired. Create a new session."}), 400
    except RuntimeError as e:
        logger.error(f"Session check failed: {e}")
        return jsonify({"error": "service_unavailable", "message": str(e)}), 503

    # Dispatch task
    try:
        task = process_chat.delay(session_id, user_message)
        logger.info(f"Task dispatched — task_id: {task.id} | session: {session_id}")
        return jsonify({"task_id": task.id}), 202
    except Exception as e:
        logger.error(f"Failed to dispatch Celery task: {e}")
        return jsonify({"error": "task_dispatch_failed", "message": "Could not queue your request. Please try again."}), 503


@bp.route("/result/<task_id>", methods=["GET"])
def get_result(task_id):
    try:
        from app.tasks import celery_app
        task = celery_app.AsyncResult(task_id)

        if task.state == "PENDING":
            return jsonify({"status": "pending"}), 202

        if task.state == "STARTED":
            return jsonify({"status": "pending"}), 202

        if task.state == "SUCCESS":
            result = task.result
            if result.get("status") == "error":
                logger.warning(f"Task {task_id} completed with error: {result.get('answer')}")
            else:
                logger.info(f"Task {task_id} result delivered successfully")
            return jsonify(result), 200

        if task.state == "FAILURE":
            logger.error(f"Task {task_id} failed with state FAILURE")
            return jsonify({
                "status": "error",
                "answer": "Task failed unexpectedly. Please try again.",
                "sources": []
            }), 500

        # Any other state
        logger.warning(f"Task {task_id} in unexpected state: {task.state}")
        return jsonify({"status": "pending"}), 202

    except Exception as e:
        logger.error(f"Error retrieving result for task {task_id}: {e}")
        return jsonify({"error": "result_fetch_failed", "message": str(e)}), 500