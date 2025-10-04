"""
QR Code Generator Service - Built with Hive Application Toolkit.

Simple stateless API service for generating QR codes from text.
Migrated to use hive-app-toolkit for production-grade quality.
"""

import base64
from io import BytesIO

import qrcode
from fastapi import HTTPException
from pydantic import BaseModel

from hive_app_toolkit import create_hive_app
from hive_logging import get_logger

logger = get_logger(__name__)

# ============================================================================
# Production-grade FastAPI app (from hive-app-toolkit)
# ============================================================================

app = create_hive_app(
    title="QR Code Generator Service",
    description="Simple stateless API for generating QR codes with production monitoring",
    version="1.0.0",
    enable_cors=True,
    enable_metrics=True,
)

# ============================================================================
# Request/Response Models
# ============================================================================


class QRRequest(BaseModel):
    """Request model for QR code generation."""

    text: str


class QRResponse(BaseModel):
    """Response model with base64-encoded QR code."""

    qr_code: str


# ============================================================================
# QR Code Generation Endpoints
# ============================================================================


@app.post("/generate", response_model=QRResponse)
async def generate_qr_code(request: QRRequest):
    """Generate a QR code from text and return as base64 PNG."""
    if not request.text:
        raise HTTPException(status_code=422, detail="Text field is required")

    logger.info(f"Generating QR code for text of length {len(request.text)}")

    try:
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(request.text)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        logger.debug("QR code generated successfully")
        return QRResponse(qr_code=img_str)

    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"QR code generation failed: {e}") from e


# Note: Health endpoints (/health, /health/live, /health/ready) are automatically
# provided by hive-app-toolkit's create_hive_app()

# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
