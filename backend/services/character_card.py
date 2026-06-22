"""
Character card import — convert SillyTavern / Janitor character cards into
ClawFans Character fields.

Cards come in two shapes (both handled by the endpoint before this is called,
but `card_to_character_fields` also tolerates a top-level `data` wrapper):
  - v2 wrapper: {"spec": "chara_card_v2", "data": {...}}
  - flat:       {name, description, personality, scenario, first_mes, mes_example}

This module is a pure function so it can be unit-tested without HTTP.
"""
from typing import Any


def _clean(value: Any) -> str:
    """Coerce a card field to a stripped string ("" for None/missing)."""
    if value is None:
        return ""
    return str(value).strip()


def card_to_character_fields(card: dict) -> dict:
    """
    Map a character card dict → ClawFans Character field dict.

    Returns keys: name, system_prompt, greeting, description.

    Raises ValueError if the card has no (non-empty) name.
    """
    # Tolerate a v2 wrapper even if the caller didn't unwrap it.
    data = card.get("data") if isinstance(card.get("data"), dict) else card

    name = _clean(data.get("name"))
    if not name:
        raise ValueError("Character card is missing a required 'name'")

    personality = _clean(data.get("personality"))
    description = _clean(data.get("description"))
    scenario = _clean(data.get("scenario"))
    mes_example = _clean(data.get("mes_example"))
    first_mes = _clean(data.get("first_mes"))

    # Assemble labeled system_prompt sections, skipping empty ones.
    sections: list[str] = []
    if personality:
        sections.append(f"Personality: {personality}")
    if description:
        sections.append(f"Appearance/Description: {description}")
    if scenario:
        sections.append(f"Scenario: {scenario}")
    if mes_example:
        sections.append(f"Example dialogue:\n{mes_example}")

    system_prompt = "\n".join(sections).strip()
    # Guarantee non-empty: fall back to a minimal persona line.
    if not system_prompt:
        system_prompt = f"You are {name}."

    greeting = first_mes or "Hello!"

    # Short description: first 150 chars of the card description, else the name.
    short_description = (description or name)[:150]

    return {
        "name": name,
        "system_prompt": system_prompt,
        "greeting": greeting,
        "description": short_description,
    }
