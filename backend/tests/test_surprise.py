"""
Variable-reward "她给你的惊喜" (daily surprise / gacha).

The strongest behavioral hook in companion products: intermittent variable
reinforcement. Each day the user can open ONE free surprise of random rarity
(common → legendary); rarer pulls grant more intimacy (and, in the endpoint,
a bolder message / image). Rarity weights are operator-tunable (the lever that
controls dopamine cadence + future monetization). Once per calendar day so the
anticipation resets daily.
"""
import random

from models.database import Character, Conversation
from services.ops_config import set_ops_values


def _seed(db, intimacy=0, last_surprise=None):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    conv = Conversation(
        character_id=char.id, title="t",
        intimacy_level=intimacy, last_surprise_date=last_surprise,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


# ── Weighted draw ─────────────────────────────────────────────────────────────

def test_draw_rarity_returns_a_pool_key():
    from services.surprise import draw_rarity
    r = draw_rarity({"common": 60, "rare": 28, "epic": 10, "legendary": 2},
                    rng=random.Random(1))
    assert r in {"common", "rare", "epic", "legendary"}


def test_draw_rarity_respects_weights():
    """All weight on one rarity → always that rarity."""
    from services.surprise import draw_rarity
    rng = random.Random(123)
    for _ in range(20):
        assert draw_rarity({"common": 0, "rare": 0, "epic": 0, "legendary": 1}, rng) == "legendary"


# ── Daily draw ────────────────────────────────────────────────────────────────

def test_first_draw_of_day_grants_rarity_and_intimacy(db):
    from services.surprise import perform_surprise
    conv = _seed(db, intimacy=10)
    # Force a legendary so the bonus is deterministic.
    set_ops_values(db, {"surprise_rarity_weights": {"common": 0, "rare": 0, "epic": 0, "legendary": 1}})

    reward = perform_surprise(conv, db, "2026-06-01", rng=random.Random(1))
    assert reward is not None
    assert reward["rarity"] == "legendary"
    assert reward["intimacy_bonus"] > 0
    db.refresh(conv)
    assert conv.intimacy_level == 10 + reward["intimacy_bonus"]
    assert conv.last_surprise_date == "2026-06-01"


def test_second_draw_same_day_unavailable(db):
    from services.surprise import perform_surprise
    conv = _seed(db, intimacy=10, last_surprise="2026-06-01")
    assert perform_surprise(conv, db, "2026-06-01", rng=random.Random(1)) is None


def test_disabled_lever_blocks_draw(db):
    from services.surprise import perform_surprise
    conv = _seed(db, intimacy=10)
    set_ops_values(db, {"surprise_enabled": False})
    assert perform_surprise(conv, db, "2026-06-01", rng=random.Random(1)) is None


# ── Endpoint ──────────────────────────────────────────────────────────────────

def test_surprise_endpoint_draws_once_per_day(client, db):
    char = Character(name="C", system_prompt="p", greeting="hi", category="Featured")
    db.add(char)
    db.commit()
    db.refresh(char)
    auth = {"Authorization": "Bearer alice"}
    conv_id = client.post(
        "/api/chat/conversations", json={"character_id": char.id}, headers=auth
    ).json()["id"]

    r = client.post(f"/api/chat/conversations/{conv_id}/surprise", headers=auth)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["available"] is True
    assert j["rarity"] in {"common", "rare", "epic", "legendary"}
    assert j["message"]  # rarity-scaled in-character line (stubbed in tests)

    # Second draw same day → unavailable.
    r2 = client.post(f"/api/chat/conversations/{conv_id}/surprise", headers=auth)
    assert r2.json()["available"] is False
