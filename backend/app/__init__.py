"""Flask app factory."""
from flask import Flask, jsonify, request
from flask_cors import CORS

from app.policy import load_policy


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    # Load policy once at startup — it's read-only and shared across requests.
    policy = load_policy()

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/claims/evaluate")
    def evaluate():
        from app.models import ClaimRequest
        from app.orchestrator import evaluate as run_pipeline

        body = request.get_json(force=True, silent=True)
        if not body:
            return jsonify(error="empty_body"), 400

        try:
            claim = ClaimRequest.model_validate(body)
        except Exception as exc:
            return jsonify(error="invalid_request", detail=str(exc)), 422

        decision = run_pipeline(claim, policy)
        return jsonify(decision.model_dump(mode="json"))

    return app
