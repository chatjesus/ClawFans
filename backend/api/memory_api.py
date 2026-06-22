"""
Memory CRUD API — lets a user see and manage what a character "remembers"
about them (人性需求: 被理解 + 掌控).

Surfaces the per-(user, character) facts stored in `UserMemory`. All endpoints
require a real (non-anonymous) user; users may only read/modify their OWN
memories.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db, UserMemory
from auth.clerk import get_current_user_id, require_auth

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ── Schemas (defined inline; we don't touch models/schemas.py) ───────────────

class MemoryResponse(BaseModel):
    id: int
    key: str
    value: str
    confidence: Optional[float] = None
    created_at: Optional[datetime] = None


class MemoryUpdate(BaseModel):
    value: str


def _serialize(mem: UserMemory) -> MemoryResponse:
    return MemoryResponse(
        id=mem.id,
        key=mem.key,
        value=mem.value,
        confidence=mem.confidence,
        created_at=mem.created_at,
    )


def _get_owned_memory(memory_id: int, user_id: str, db: Session) -> UserMemory:
    """Fetch a memory, enforcing existence (404) then ownership (403)."""
    mem = db.query(UserMemory).filter(UserMemory.id == memory_id).first()
    if mem is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if mem.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your memory")
    return mem


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    request: Request,
    character_id: int = Query(..., description="Character whose memories to list"),
    db: Session = Depends(get_db),
):
    """List the requesting user's memories for a given character."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    mems = (
        db.query(UserMemory)
        .filter(
            UserMemory.user_id == user_id,
            UserMemory.character_id == character_id,
        )
        .all()
    )
    return [_serialize(m) for m in mems]


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update the value of one of the caller's own memories."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    mem = _get_owned_memory(memory_id, user_id, db)
    mem.value = payload.value
    db.commit()
    db.refresh(mem)
    return _serialize(mem)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete one of the caller's own memories."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    mem = _get_owned_memory(memory_id, user_id, db)
    db.delete(mem)
    db.commit()
    return Response(status_code=204)
