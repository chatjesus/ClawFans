"""
Character management API – CRUD operations for AI characters.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from models.database import get_db, Character
from models.schemas import (
    CharacterCreate, CharacterUpdate, CharacterResponse, CharacterCard
)

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.post("/", response_model=CharacterResponse, status_code=201)
def create_character(data: CharacterCreate, db: Session = Depends(get_db)):
    """Create a new AI character."""
    char = Character(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        greeting=data.greeting,
        avatar_url=data.avatar_url,
        tags=data.tags,
        category=data.category,
        is_public=data.is_public,
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char


@router.get("/", response_model=list[CharacterCard])
def list_characters(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List characters with optional category filter and search."""
    query = db.query(Character).filter(Character.is_public == True)

    if category and category.lower() != "featured":
        query = query.filter(Character.category == category)

    if search:
        query = query.filter(
            Character.name.ilike(f"%{search}%")
            | Character.description.ilike(f"%{search}%")
            | Character.tags.ilike(f"%{search}%")
        )

    query = query.order_by(Character.message_count.desc())
    return query.offset(skip).limit(limit).all()


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    """Return all distinct categories."""
    rows = db.query(Character.category).distinct().all()
    categories = ["Featured"] + sorted(
        set(r[0] for r in rows if r[0] and r[0] != "Featured")
    )
    return categories


@router.get("/{character_id}", response_model=CharacterResponse)
def get_character(character_id: int, db: Session = Depends(get_db)):
    """Get a single character by ID."""
    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    return char


@router.put("/{character_id}", response_model=CharacterResponse)
def update_character(
    character_id: int,
    data: CharacterUpdate,
    db: Session = Depends(get_db),
):
    """Update a character."""
    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(char, key, value)

    db.commit()
    db.refresh(char)
    return char


@router.delete("/{character_id}", status_code=204)
def delete_character(character_id: int, db: Session = Depends(get_db)):
    """Delete a character."""
    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    db.delete(char)
    db.commit()

