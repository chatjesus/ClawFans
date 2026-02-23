"""Upload API endpoint for avatar images.
Uploads to Cloudflare R2 when R2 credentials are configured, otherwise falls
back to local disk storage (useful for development).
"""
import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "avatars")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_SIZE      = 10 * 1024 * 1024  # 10 MB

# ── R2 configuration (optional) ───────────────────────────────────────────────
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY", "")
R2_BUCKET     = os.environ.get("R2_BUCKET",     "clawfans")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL",  "https://assets.tinyclaw.dev")

_r2_client = None


def _get_r2():
    """Lazy-init the S3/R2 client. Returns None when credentials are absent."""
    global _r2_client
    if _r2_client is not None:
        return _r2_client
    if not (R2_ACCOUNT_ID and R2_ACCESS_KEY and R2_SECRET_KEY):
        return None
    try:
        import boto3
        _r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto",
        )
        logger.info("R2 client initialised (bucket=%s)", R2_BUCKET)
    except Exception as e:
        logger.warning("R2 client init failed: %s – falling back to local storage", e)
    return _r2_client


@router.post("/upload/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    """Upload an avatar image. Returns the public URL."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Allowed: jpg, png, gif, webp",
        )

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size: 10MB")

    ext      = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"

    r2 = _get_r2()
    if r2:
        # ── Upload to R2 ──────────────────────────────────────────────────────
        key = f"uploads/avatars/{filename}"
        try:
            r2.put_object(
                Bucket=R2_BUCKET,
                Key=key,
                Body=contents,
                ContentType=file.content_type,
                CacheControl="public, max-age=31536000",
            )
            url = f"{R2_PUBLIC_URL}/{key}"
            logger.info("Avatar uploaded to R2: %s", url)
            return JSONResponse({"url": url})
        except Exception as e:
            logger.error("R2 upload failed: %s – falling back to local disk", e)

    # ── Fallback: local disk ──────────────────────────────────────────────────
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    return JSONResponse({"url": f"/uploads/avatars/{filename}"})
