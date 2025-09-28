"""
Health check endpoints for {{project_name}}
"""

from flask import Blueprint, jsonify
import os

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify(
        {
            "status": "healthy",
            "service": "{{project_name}}",
            "version": "1.0.0",
            "environment": os.environ.get("FLASK_ENV", "production"),
        }
    )


@health_bp.route("/api/info", methods=["GET"])
def app_info():
    """Application information endpoint"""
    return jsonify(
        {
            "name": "{{project_name}}",
            "description": "{{project_description}}",
            "version": "1.0.0",
            "python_version": "3.10+",
            "framework": "Flask",
            "features": {"cors": True, "logging": True, "monitoring": True},
        }
    )
