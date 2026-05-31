"""
The project uses Base.metadata.create_all() and has no Alembic. create_all
only creates missing TABLES — it never adds COLUMNS to a table that already
exists. So when a column is added to a model (e.g. clerk_creator_id,
voice_id), existing databases drift and every query of that table dies with
`no such column`.

Contract: a lightweight forward-migration adds any model columns missing
from existing tables, preserving the rows already there.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


def test_missing_columns_added_to_existing_table_preserving_rows():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # Simulate an OLD schema: characters table predates clerk_creator_id / voice_id.
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE characters ("
            " id INTEGER PRIMARY KEY, name VARCHAR(100), system_prompt TEXT,"
            " message_count INTEGER DEFAULT 0)"
        ))
        c.execute(text(
            "INSERT INTO characters (id, name, system_prompt, message_count)"
            " VALUES (1, 'Luna', 'p', 42)"
        ))

    from models.database import ensure_columns
    ensure_columns(eng)

    with eng.connect() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(characters)")).fetchall()}
        # Pre-existing row + a query touching the new column must both work.
        row = c.execute(
            text("SELECT name, message_count, clerk_creator_id, voice_id"
                 " FROM characters WHERE id = 1")
        ).first()

    assert "clerk_creator_id" in cols
    assert "voice_id" in cols
    assert row.name == "Luna"
    assert row.message_count == 42  # existing data preserved


def test_ensure_columns_is_noop_on_current_schema():
    """Running twice (or on an already-current table) must not error."""
    from models.database import Base, ensure_columns

    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=eng)
    ensure_columns(eng)  # first run — nothing missing
    ensure_columns(eng)  # idempotent second run
