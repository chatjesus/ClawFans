"""
P1-7 — listing characters with a locale must not be O(N) queries.

list_characters → _apply_locale_card touches char.translations for every
row. Without eager loading that's one extra SELECT per character (classic
N+1). With 300 characters x lazy translation loads, the gallery page hits
the DB hundreds of times per request.

Contract: the number of SELECTs is bounded and does NOT grow with the
number of characters returned.
"""
from sqlalchemy import event

from models.database import Character, CharacterTranslation


def _seed_many(db, n: int):
    for i in range(n):
        c = Character(
            name=f"C{i}", system_prompt="x", description="d", category="Featured"
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        db.add(
            CharacterTranslation(
                character_id=c.id, locale="en", description=f"en desc {i}"
            )
        )
        db.commit()


def _count_selects_during(engine, fn):
    selects: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _ctx, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(engine, "after_cursor_execute", _listener)
    try:
        fn()
    finally:
        event.remove(engine, "after_cursor_execute", _listener)
    return selects


def test_list_characters_with_locale_is_constant_queries(client, db, engine):
    _seed_many(db, 6)

    result = {}

    def _do():
        r = client.get("/api/characters/?locale=en")
        result["status"] = r.status_code
        result["count"] = len(r.json())

    selects = _count_selects_during(engine, _do)

    assert result["status"] == 200
    assert result["count"] == 6
    assert len(selects) <= 3, (
        f"N+1 detected: {len(selects)} SELECTs for 6 characters with translations. "
        f"Expected a bounded count via eager loading."
    )
