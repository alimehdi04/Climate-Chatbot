from flask import Blueprint, request, jsonify
from app.session import create_session, delete_session, session_exists
from app.tasks import process_chat

bp = Blueprint("api", __name__)


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@bp.route("/session", methods=["POST"])
def new_session():
    session_id = create_session()
    return jsonify({"session_id": session_id}), 201


@bp.route("/session/<session_id>", methods=["DELETE"])
def end_session(session_id):
    if not session_exists(session_id):
        return jsonify({"error": "Session not found"}), 404
    delete_session(session_id)
    return jsonify({"message": "Session cleared"}), 200


@bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    session_id  = data.get("session_id")
    user_message = data.get("message", "").strip()

    if not session_id or not session_exists(session_id):
        return jsonify({"error": "Invalid or missing session_id"}), 400

    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    task = process_chat.delay(session_id, user_message)
    return jsonify({"task_id": task.id}), 202


@bp.route("/result/<task_id>", methods=["GET"])
def get_result(task_id):
    from app.tasks import celery_app
    task = celery_app.AsyncResult(task_id)

    if task.state == "PENDING":
        return jsonify({"status": "pending"}), 202

    if task.state == "SUCCESS":
        return jsonify(task.result), 200

    return jsonify({"status": "error", "answer": "Task failed"}), 500