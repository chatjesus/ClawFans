"""
Scene Pre-generation Service — generates 5 scene images per character in background.

Triggered on first conversation with a character. Scenes are served instantly
via [SCENE:n] tags, eliminating wait time for the first ~5 image moments.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from services.image_service import (
    generate_image_gemini,
    _resolve_avatar_bytes,
    get_char_ref_bytes,
    get_scene_dir,
    scenes_ready,
    get_pregenerated_scenes,
    REFS_DIR,
    BACKEND_DIR,
)
from services.llm_service import chat_completion

logger = logging.getLogger(__name__)

NUM_SCENES = 5

_generation_locks: dict[int, asyncio.Lock] = {}


def _get_lock(character_id: int) -> asyncio.Lock:
    if character_id not in _generation_locks:
        _generation_locks[character_id] = asyncio.Lock()
    return _generation_locks[character_id]


SCENE_PLANNER_PROMPT = """\
You are a scene designer for a visual novel / AI chat platform.
Given a character's name, description, and personality, generate exactly {n} scene descriptions
for images that would appear naturally during their first few chat interactions.

Requirements:
- Scene 0: Character portrait/selfie in their signature setting (the greeting moment)
- Scene 1: Character showing emotion relevant to their personality (warm/inviting/mysterious)
- Scene 2: A meaningful location or environment shot featuring the character
- Scene 3: Character in an action or pose that reveals personality
- Scene 4: An intimate or dramatic moment (the emotional climax)

Each description must:
- Start with the character's physical traits (hair, eyes, build, clothes) for visual consistency
- Include pose, expression, setting, lighting, mood
- Be a single paragraph of 30-60 words
- Be an anime-style illustration prompt

Character: {name}
Description: {description}
System prompt excerpt: {system_excerpt}

Output EXACTLY {n} lines, one scene per line, numbered 0-4.
Format: N: [scene description]
"""


async def plan_scenes(
    name: str, description: str, system_prompt: str, n: int = NUM_SCENES
) -> list[str]:
    """Use LLM to generate scene descriptions tailored to the character."""
    excerpt = system_prompt[:800]
    prompt = SCENE_PLANNER_PROMPT.format(
        n=n, name=name, description=description, system_excerpt=excerpt
    )

    try:
        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error(f"Scene planning LLM call failed: {e}")
        return _fallback_scenes(name, description)

    scenes = []
    for line in response.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit() and ":" in line:
            desc = line.split(":", 1)[1].strip()
            if desc:
                scenes.append(desc)
    if len(scenes) < n:
        scenes.extend(_fallback_scenes(name, description)[len(scenes):n])
    return scenes[:n]


def _fallback_scenes(name: str, description: str) -> list[str]:
    """Generic scenes if LLM planning fails."""
    short_desc = description[:100]
    return [
        f"anime portrait, {short_desc}, looking at viewer, warm smile, soft lighting, upper body, detailed face",
        f"anime illustration, {short_desc}, expressive face, emotional moment, gentle atmosphere, bokeh background",
        f"anime landscape with character, {short_desc}, standing in their signature setting, atmospheric lighting, wide shot",
        f"anime illustration, {short_desc}, dynamic pose showing personality, dramatic lighting, detailed",
        f"anime illustration, {short_desc}, intimate close-up, vulnerable expression, warm golden hour light, cinematic",
    ]


async def pregenerate_scenes(
    character_id: int,
    name: str,
    description: str,
    system_prompt: str,
    avatar_url: Optional[str] = None,
) -> dict[int, str]:
    """
    Generate 5 scene images for a character. Skips already-generated scenes.
    Returns {scene_index: url_path}.
    """
    lock = _get_lock(character_id)
    async with lock:
        existing = get_pregenerated_scenes(character_id)
        if len(existing) >= NUM_SCENES:
            logger.info(f"Scenes already ready for character {character_id}")
            return existing

        scene_dir = get_scene_dir(character_id)
        # Prefer dedicated portrait reference over avatar thumbnail
        ref_bytes = get_char_ref_bytes(character_id) or _resolve_avatar_bytes(avatar_url)

        scene_descs = await plan_scenes(name, description, system_prompt)
        logger.info(f"Generating {NUM_SCENES} scenes for '{name}' (id={character_id})...")

        results = dict(existing)
        for i, desc in enumerate(scene_descs):
            if i in existing:
                continue

            url = None
            for attempt in range(3):
                url = await generate_image_gemini(
                    desc,
                    reference_image=ref_bytes,
                    output_dir=scene_dir,
                    filename_prefix=f"scene_{i}_",
                )
                if url:
                    break
                logger.info(f"  Scene {i} attempt {attempt+1} failed, retrying...")
                await asyncio.sleep(2 * (attempt + 1))

            if url:
                src = BACKEND_DIR / url.lstrip("/")
                ext = src.suffix
                canonical = scene_dir / f"scene_{i}{ext}"
                if src != canonical:
                    src.rename(canonical)
                    rel = canonical.relative_to(BACKEND_DIR)
                    url = f"/{rel.as_posix()}"
                results[i] = url
                logger.info(f"  Scene {i}/{NUM_SCENES-1} done: {url}")
            else:
                logger.warning(f"  Scene {i} generation failed after retries")

        logger.info(f"Scene pre-generation complete: {len(results)}/{NUM_SCENES} for '{name}'")
        return results


async def ensure_scenes_background(
    character_id: int,
    name: str,
    description: str,
    system_prompt: str,
    avatar_url: Optional[str] = None,
):
    """Fire-and-forget: start scene pre-generation in background if not ready."""
    if scenes_ready(character_id):
        return
    try:
        await pregenerate_scenes(character_id, name, description, system_prompt, avatar_url)
    except Exception as e:
        logger.error(f"Background scene generation failed for {character_id}: {e}")


def build_scene_availability_prompt(character_id: int) -> str:
    """Build a system prompt fragment describing available pre-generated scenes."""
    scenes = get_pregenerated_scenes(character_id)
    if not scenes:
        return ""
    lines = [
        "\n## Pre-generated Scene Images (INSTANT delivery)",
        "The following scene images are pre-generated and can be shown INSTANTLY (no wait).",
        "Use [SCENE:N] to include one. These are much faster than [IMG:] tags.",
        "Use them in your first few messages for a great experience:",
    ]
    for idx in sorted(scenes.keys()):
        lines.append(f"  - [SCENE:{idx}] — Scene image #{idx}")
    lines.append(
        "Use [SCENE:N] for these instant images. "
        "Use [IMG: description] only for custom scenes not covered above."
    )
    return "\n".join(lines)
