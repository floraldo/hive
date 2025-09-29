"""
{{project_name}} API
{{project_description}}
"""

import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from hive_logging import get_logger

# Load environment variables
load_dotenv()

# Setup structured logging
logger = get_logger("{{project_name}}")

app = Flask(__name__)
CORS(app)

# Load configuration from environment
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["DEBUG"] = os.environ.get("FLASK_ENV") == "development"

# Register blueprints
from api.health import health_bp

app.register_blueprint(health_bp)

# Register additional API blueprints
# from api.your_module import your_bp
# app.register_blueprint(your_bp)


@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {error}")
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    logger.info(f"Starting {{project_name}} on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
