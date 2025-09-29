"""Guardian Agent API using Hive Application Toolkit."""

import hmac
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Header, HTTPException, Request
from guardian_agent.core.config import GuardianConfig
from guardian_agent.cost_calculator import GuardianCostCalculator
from guardian_agent.learning.review_history import ReviewHistory
from guardian_agent.review.engine import ReviewEngine
from guardian_agent.webhooks.github_handler import GitHubWebhookHandler
from pydantic import BaseModel, Field

from hive_app_toolkit.api import create_hive_app
from hive_app_toolkit.cost import with_cost_tracking
from hive_logging import get_logger

logger = get_logger(__name__)

# Initialize configuration
config = GuardianConfig()
config.validate()

# Create Hive app with production configuration
app = create_hive_app(
    title="Guardian Agent API",
    description="AI-powered code review service for the Hive platform",
    version="1.0.0",
    cost_calculator=GuardianCostCalculator(),
    daily_cost_limit=100.0,
    monthly_cost_limit=2000.0,
    rate_limits={
        "per_minute": 20,
        "per_hour": 100,
        "concurrent": 5,
    },
    enable_cors=True,
    enable_metrics=True,
)

# Initialize business logic components
review_engine = ReviewEngine(config)
github_handler = GitHubWebhookHandler(config)
review_history = ReviewHistory(config.learning.history_path)


# ============================================================================
# Request/Response Models
# ============================================================================


class ReviewRequest(BaseModel):
    """Request model for manual review trigger."""

    file_paths: list[str] = Field(..., description="List of file paths to review")
    review_type: str = Field("full", description="Type of review: full, quick, security")
    context: dict[str, Any] | None = Field(None, description="Additional context")


class ReviewResponse(BaseModel):
    """Response model for review results."""

    review_id: str
    status: str
    results: list[dict[str, Any]]
    summary: dict[str, Any]
    cost: float
    timestamp: str


class FeedbackRequest(BaseModel):
    """Request model for feedback submission."""

    review_id: str
    violation_id: str | None = None
    feedback_type: str = Field(..., description="positive, negative, false_positive")
    feedback_text: str | None = None


# Note: HealthResponse and CostReportResponse are provided by hive-app-toolkit


# Note: Basic health endpoints (/health, /health/live, /health/ready) are provided by hive-app-toolkit
# Custom health checks for Guardian Agent components can be added here if needed


# ============================================================================
# Review Endpoints
# ============================================================================


@app.post("/api/review", response_model=ReviewResponse)
@with_cost_tracking("file_review")
async def trigger_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Manually trigger a code review."""
    try:
        review_id = f"review_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        files = [Path(fp) for fp in request.file_paths]

        # Note: Cost tracking and rate limiting handled by @with_cost_tracking decorator
        async def run_review():
            try:
                start_time = datetime.now()
                results = []

                for file_path in files:
                    result = await review_engine.review_file(file_path)
                    results.append(result.to_dict())

                # Save to history
                await review_history.save_review(
                    {
                        "review_id": review_id,
                        "files": request.file_paths,
                        "results": results,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Review {review_id} completed in {execution_time:.2f}s")

            except Exception as e:
                logger.error(f"Review failed: {e}")

        # Run review in background
        background_tasks.add_task(run_review)

        return ReviewResponse(
            review_id=review_id,
            status="processing",
            results=[],
            summary={"message": "Review started in background"},
            cost=0.0,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Review trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/review/{review_id}")
async def get_review_status(review_id: str):
    """Get status of a specific review."""
    try:
        review = await review_history.get_review(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        return review
    except Exception as e:
        logger.error(f"Failed to get review status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GitHub Webhook Endpoint
# ============================================================================


@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
):
    """Handle GitHub webhook events."""
    try:
        # Get payload
        payload = await request.json()

        # Verify signature if configured
        if config.github_webhook_secret and x_hub_signature_256:
            body = await request.body()
            expected_sig = hmac.new(
                config.github_webhook_secret.encode(),
                body,
                "sha256",
            ).hexdigest()

            if not hmac.compare_digest(
                f"sha256={expected_sig}",
                x_hub_signature_256,
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Check event type
        event_type = request.headers.get("X-GitHub-Event")
        if event_type not in ["pull_request", "issue_comment"]:
            return {"status": "ignored", "reason": f"Event {event_type} not supported"}

        # Handle in background
        async def process_webhook():
            try:
                result = await github_handler.handle_webhook(payload, dict(request.headers))
                logger.info(f"Webhook processed: {result}")
            except Exception as e:
                logger.error(f"Webhook processing failed: {e}")

        background_tasks.add_task(process_webhook)

        return {"status": "accepted", "message": "Webhook will be processed"}

    except Exception as e:
        logger.error(f"Webhook handler failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Feedback Endpoints
# ============================================================================


@app.post("/api/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """Submit feedback on a review."""
    try:
        # Save feedback to history
        await review_history.save_feedback(
            {
                "review_id": feedback.review_id,
                "violation_id": feedback.violation_id,
                "feedback_type": feedback.feedback_type,
                "feedback_text": feedback.feedback_text,
                "timestamp": datetime.now().isoformat(),
            }
        )

        metrics.increment(f"feedback_{feedback.feedback_type}")

        return {
            "status": "success",
            "message": "Feedback recorded",
            "feedback_id": f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }

    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/stats")
async def get_feedback_stats():
    """Get feedback statistics."""
    try:
        stats = await review_history.get_feedback_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Note: Standard metrics endpoints (/api/metrics, /api/metrics/prometheus, /api/cost-report)
# are provided by hive-app-toolkit automatically


# ============================================================================
# Admin Endpoints
# ============================================================================


@app.post("/api/admin/clear-cache")
async def clear_cache():
    """Clear Guardian Agent specific caches."""
    try:
        if review_engine.cache:
            await review_engine.cache.clear()
        return {"status": "success", "message": "Guardian Agent cache cleared"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Note: /api/admin/reset-limits is provided by hive-app-toolkit


# Note: Startup/shutdown events and uvicorn runner are handled by hive-app-toolkit
# Custom initialization can be added using the toolkit's lifecycle hooks if needed
