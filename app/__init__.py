from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from app.logger import get_logger

logger = get_logger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)

    from app.routes import bp
    app.register_blueprint(bp)

    # Global error handlers — catch anything not handled in routes
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": "Endpoint does not exist"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "method_not_allowed", "message": "HTTP method not allowed for this endpoint"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Unhandled internal server error: {e}")
        return jsonify({"error": "internal_server_error", "message": "An unexpected error occurred"}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        logger.error(f"Unhandled exception: {type(e).__name__}: {e}")
        return jsonify({"error": "internal_server_error", "message": "An unexpected error occurred"}), 500

    logger.info(f"Flask app created — ENV: {Config.DEBUG and 'development' or 'production'}")
    return app