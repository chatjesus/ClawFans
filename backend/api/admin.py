"""
Admin API — read/update the configurable adult-operations layer.

Gate: if env OPS_ADMIN_TOKEN is set, requests must send a matching
`X-Admin-Token` header (operators in production). If it's unset (local dev),
the endpoints are open. Keep the token out of source — set it in the
environment of the deployment.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from models.database import get_db
from services.ops_config import get_ops_config, set_ops_values

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(request: Request) -> None:
    token = os.getenv("OPS_ADMIN_TOKEN")
    if not token:
        return  # dev: no gate configured
    if request.headers.get("X-Admin-Token") != token:
        raise HTTPException(status_code=403, detail="admin only")


@router.get("/ops-config")
def read_ops_config(request: Request, db: Session = Depends(get_db)) -> dict:
    """Return the full operations config (defaults overlaid with overrides)."""
    _require_admin(request)
    return get_ops_config(db)


@router.put("/ops-config")
async def update_ops_config(request: Request, db: Session = Depends(get_db)) -> dict:
    """Update one or more levers. Body is a flat {key: value} object. Unknown
    keys are stored too (forward-compatible). Returns the merged config."""
    _require_admin(request)
    updates = await request.json()
    if not isinstance(updates, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return set_ops_values(db, updates)
