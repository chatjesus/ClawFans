"""
Character management API – CRUD operations for AI characters.
Supports ?locale= parameter to overlay translated content.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from models.database import get_db, Character, CharacterTranslation
from models.schemas import (
    CharacterCreate, CharacterUpdate, CharacterResponse, CharacterCard
)
from auth.clerk import get_current_user_id, require_auth

router = APIRouter(prefix="/api/characters", tags=["characters"])

SUPPORTED_LOCALES = {
    "en", "zh", "zh-TW",
    "ja", "ko",
    "es", "fr", "pt", "de", "ru", "it",
    "th", "vi", "id", "ar",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_best_translation(
    char: Character, locale: str
) -> Optional[CharacterTranslation]:
    """
    Find the best available translation with fallback chain:
      requested locale → English → None (use original Chinese)
    """
    tr_map = {t.locale: t for t in char.translations}

    # Exact match
    tr = tr_map.get(locale)
    if tr:
        return tr

    # English fallback (better than raw Chinese for non-Chinese users)
    if locale != "en":
        tr = tr_map.get("en")
        if tr:
            return tr

    return None  # Fall through to original Chinese


def _require_owner(char: Character, user_id: str) -> None:
    """Raise 403 unless ``user_id`` created this character. Characters with no
    clerk_creator_id (seed / legacy) are system-owned and editable by no one
    through the API."""
    if char.clerk_creator_id != user_id:
        raise HTTPException(status_code=403, detail="Not the character's creator")


def _apply_locale(char: Character, locale: Optional[str]) -> Character:
    """
    Overlay translated fields with fallback chain:
      requested locale → English → Chinese (original)
    """
    if not locale or locale in ("zh", "zh-CN"):
        return char  # Simplified Chinese is the native language
    if locale not in SUPPORTED_LOCALES:
        return char

    tr = _get_best_translation(char, locale)
    if not tr:
        return char

    if tr.description:
        char.description = tr.description
    if tr.greeting:
        char.greeting = tr.greeting
    if tr.system_prompt:
        char.system_prompt = tr.system_prompt
    return char


def _apply_locale_card(char: Character, locale: Optional[str]) -> Character:
    """Overlay description only (for card listing), with English fallback."""
    if not locale or locale in ("zh", "zh-CN"):
        return char
    if locale not in SUPPORTED_LOCALES:
        return char

    tr = _get_best_translation(char, locale)
    if tr and tr.description:
        char.description = tr.description
    return char


# ── Character CRUD ────────────────────────────────────────────────────────────

@router.post("/", response_model=CharacterResponse, status_code=201)
async def create_character(
    data: CharacterCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a new AI character. Requires auth — caller becomes the creator."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    char = Character(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        greeting=data.greeting,
        avatar_url=data.avatar_url,
        tags=data.tags,
        category=data.category,
        is_public=data.is_public,
        clerk_creator_id=user_id,
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char


@router.get("/", response_model=list[CharacterCard])
def list_characters(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    locale: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
):
    """List characters with optional category filter, search, and locale overlay."""
    query = db.query(Character).filter(Character.is_public == True)

    # Eager-load translations so the per-row _apply_locale_card overlay below
    # doesn't trigger a separate SELECT per character (N+1).
    if locale and locale != "zh":
        from sqlalchemy.orm import selectinload
        query = query.options(selectinload(Character.translations))

    if category and category.lower() != "featured":
        query = query.filter(Character.category == category)

    if search:
        query = query.filter(
            Character.name.ilike(f"%{search}%")
            | Character.description.ilike(f"%{search}%")
            | Character.tags.ilike(f"%{search}%")
        )

    query = query.order_by(
        Character.sort_weight.desc(),
        Character.message_count.desc(),
        Character.created_at.desc(),
    )
    chars = query.offset(skip).limit(limit).all()

    if locale and locale != "zh":
        chars = [_apply_locale_card(c, locale) for c in chars]

    return chars


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    """Return all distinct categories."""
    rows = db.query(Character.category).distinct().all()
    categories = ["Featured"] + sorted(
        set(r[0] for r in rows if r[0] and r[0] != "Featured")
    )
    return categories


@router.get("/{character_id}", response_model=CharacterResponse)
def get_character(
    character_id: int,
    locale: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get a single character, with optional locale overlay."""
    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    return _apply_locale(char, locale)


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: int,
    data: CharacterUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Update a character. Only the creator may modify it."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    _require_owner(char, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(char, key, value)

    db.commit()
    db.refresh(char)
    return char


@router.delete("/{character_id}", status_code=204)
async def delete_character(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete a character. Only the creator may delete it."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    _require_owner(char, user_id)

    db.delete(char)
    db.commit()


# ── Translation CRUD ──────────────────────────────────────────────────────────

class TranslationUpsert(BaseModel):
    locale: str
    description: Optional[str] = None
    greeting: Optional[str] = None
    system_prompt: Optional[str] = None


class TranslationResponse(BaseModel):
    id: int
    character_id: int
    locale: str
    description: str
    greeting: str
    system_prompt: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/{character_id}/translations", response_model=list[TranslationResponse])
def list_translations(character_id: int, db: Session = Depends(get_db)):
    """List all available translations for a character."""
    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    return db.query(CharacterTranslation).filter(
        CharacterTranslation.character_id == character_id
    ).all()


@router.put("/{character_id}/translations", response_model=TranslationResponse)
async def upsert_translation(
    character_id: int,
    data: TranslationUpsert,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create or update a translation for a specific locale. Only the
    character's creator may edit its translations."""
    user_id = await get_current_user_id(request)
    require_auth(user_id)

    char = db.query(Character).filter(Character.id == character_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    _require_owner(char, user_id)
    if data.locale not in SUPPORTED_LOCALES:
        raise HTTPException(status_code=400, detail=f"Unsupported locale: {data.locale}")

    tr = db.query(CharacterTranslation).filter(
        CharacterTranslation.character_id == character_id,
        CharacterTranslation.locale == data.locale,
    ).first()

    if tr:
        if data.description is not None:
            tr.description = data.description
        if data.greeting is not None:
            tr.greeting = data.greeting
        if data.system_prompt is not None:
            tr.system_prompt = data.system_prompt
    else:
        tr = CharacterTranslation(
            character_id=character_id,
            locale=data.locale,
            description=data.description or "",
            greeting=data.greeting or "",
            system_prompt=data.system_prompt,
        )
        db.add(tr)

    db.commit()
    db.refresh(tr)
    return tr


@router.get("/{character_id}/translations/{locale}", response_model=TranslationResponse)
def get_translation(character_id: int, locale: str, db: Session = Depends(get_db)):
    """Get a single translation."""
    tr = db.query(CharacterTranslation).filter(
        CharacterTranslation.character_id == character_id,
        CharacterTranslation.locale == locale,
    ).first()
    if not tr:
        raise HTTPException(status_code=404, detail="Translation not found")
    return tr
