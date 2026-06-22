"""
Scene pre-generation must route through the NSFW-capable provider path.

`pregenerate_scenes` historically called `generate_image_gemini(...)` directly,
so the "instant" pre-generated scenes were produced by the CENSORED cloud
backend and could never be explicit — wrong for an uncensored adult product.

Contract:
- `pregenerate_scenes` routes through the provider-aware `generate_image(...)`
  (which prefers local ComfyUI/NSFW when available, else Gemini), NOT
  `generate_image_gemini` directly.
- Intimate/climax scenes (indices 3 and 4) are requested with nsfw=True; the
  earlier scenes (0–2) with nsfw=False.
- The character_id is threaded through for the reference portrait.

Also: GCP credentials must be env-only (no hardcoded personal path).
"""
import importlib

import pytest

import services.scene_service as scene_service


@pytest.fixture
def scene_workdir():
    """A unique temp scene dir *inside* BACKEND_DIR.

    The service computes URL paths via `Path.relative_to(BACKEND_DIR)`, so both
    the scene dir and the (fake) generated source files must live under
    BACKEND_DIR for the canonical-rename step to produce valid URLs. We create
    an isolated subtree and tear it down afterwards so no files leak.
    """
    import shutil
    import uuid

    root = scene_service.BACKEND_DIR / "uploads" / "_test_tmp" / uuid.uuid4().hex
    scene_dir = root / "scenes"
    gen_dir = root / "generated"
    scene_dir.mkdir(parents=True, exist_ok=True)
    gen_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield scene_dir, gen_dir
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.asyncio
async def test_pregenerate_routes_through_generate_image_with_nsfw_flags(
    scene_workdir, monkeypatch
):
    scene_dir, gen_dir = scene_workdir
    calls = []

    async def fake_plan_scenes(name, description, system_prompt, n=5):
        return [f"scene description {i}" for i in range(5)]

    async def recording_generate_image(prompt, **kwargs):
        calls.append({"prompt": prompt, "kwargs": kwargs})
        # Return a freshly created file (mimics a generated image on disk under
        # BACKEND_DIR) so the service's canonical-rename step has something to move.
        idx = len(calls) - 1
        src = gen_dir / f"gen_{idx}.png"
        src.write_bytes(b"fake-image-bytes")
        rel = src.relative_to(scene_service.BACKEND_DIR)
        return f"/{rel.as_posix()}"

    monkeypatch.setattr(scene_service, "plan_scenes", fake_plan_scenes)
    monkeypatch.setattr(scene_service, "generate_image", recording_generate_image)
    monkeypatch.setattr(scene_service, "get_scene_dir", lambda cid: scene_dir)
    # No real reference portrait / avatar lookups.
    monkeypatch.setattr(scene_service, "get_char_ref_bytes", lambda cid: None)
    monkeypatch.setattr(scene_service, "_resolve_avatar_bytes", lambda url: None)
    # Start from a clean slate (no pre-existing scenes).
    monkeypatch.setattr(scene_service, "get_pregenerated_scenes", lambda cid: {})

    result = await scene_service.pregenerate_scenes(
        character_id=42,
        name="Aria",
        description="a character",
        system_prompt="be yourself",
    )

    # Routed through generate_image once per scene (no direct gemini calls).
    assert len(calls) == 5, f"expected 5 generate_image calls, got {len(calls)}"

    # nsfw flag per scene index: intimate/climax scenes 3 & 4 are NSFW; 0–2 safe.
    nsfw_by_index = [c["kwargs"].get("nsfw") for c in calls]
    assert nsfw_by_index == [False, False, False, True, True], nsfw_by_index

    # character_id threaded through for the reference portrait.
    for c in calls:
        assert c["kwargs"].get("character_id") == 42

    # Returned dict has all five scene indices.
    assert set(result.keys()) == {0, 1, 2, 3, 4}

    # Files were renamed to the canonical scene_{i} names in the scene dir, and
    # get_pregenerated_scenes-style glob (scene_*.png) would still find them.
    for i in range(5):
        assert (scene_dir / f"scene_{i}.png").exists()
        assert result[i].endswith(f"scene_{i}.png")


def test_does_not_call_generate_image_gemini_directly():
    """The service should no longer reference generate_image_gemini directly."""
    assert not hasattr(scene_service, "generate_image_gemini"), (
        "scene_service still imports generate_image_gemini — it should route "
        "through the provider-aware generate_image instead"
    )


def test_gcp_credentials_is_env_only_when_unset(monkeypatch):
    """image_service.GCP_CREDENTIALS must default to '' (no hardcoded path)."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    import services.image_service as image_service

    image_service = importlib.reload(image_service)
    try:
        assert image_service.GCP_CREDENTIALS == "", (
            f"GCP_CREDENTIALS leaked a default path: {image_service.GCP_CREDENTIALS!r}"
        )
    finally:
        importlib.reload(image_service)
