import base64
from io import BytesIO

import qrcode
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="QR Code Generator Service")


class QRRequest(BaseModel):
    text: str


class QRResponse(BaseModel):
    qr_code: str


@app.post("/generate", response_model=QRResponse)
async def generate_qr_code(request: QRRequest):
    """Generate a QR code from text and return as base64 PNG."""
    if not request.text:
        raise HTTPException(status_code=422, detail="Text field is required")

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(request.text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()

    return QRResponse(qr_code=img_str)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
