"""
Hive Backend API
A Flask application demonstrating the Hive architecture
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Load configuration from environment
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Register weather API blueprint
from weather_api import weather_bp
app.register_blueprint(weather_bp)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    from datetime import datetime
    return jsonify({
        "status": "ok",
        "service": "backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/api/hello', methods=['GET'])
def hello():
    """Hello World endpoint"""
    from datetime import datetime
    return jsonify({
        "message": "Hello from Hive!",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "backend"
    })

@app.route('/api/info', methods=['GET'])
def app_info():
    """Application information endpoint"""
    return jsonify({
        "name": "Hive Backend",
        "description": "Multi-agent orchestration system backend",
        "version": "1.0.0",
        "environment": os.environ.get('FLASK_ENV', 'production')
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)