"""Flask app 
"""
from flask import Flask, jsonify
from flask_cors import CORS


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app) 

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/claims/evaluate")
    def evaluate():
        
        return jsonify(error="not_implemented", detail="yet to implement"), 501

    return app
