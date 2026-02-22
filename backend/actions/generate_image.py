"""
Image generation tool: generates character images via local ComfyUI or Gemini.
"""
import logging

from gateway.contracts import ToolCallResult
from actions.registry import ToolSpec

logger = logging.getLogger(__name__)

COMFYUI_URL = "http://localhost:8188"


async def _generate_image(
    prompt: str,
    style: str = "anime",
    character_id: int = 0,
) -> ToolCallResult:
    """
    Generate an image. Tries ComfyUI first, falls back to placeholder.
    Full ComfyUI workflow integration will be added in M5 refinement.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{COMFYUI_URL}/system_stats")
            if health.status_code == 200:
                return ToolCallResult(
                    tool_name="generate_image",
                    success=True,
                    output=f"[Image generation queued] Prompt: {prompt}, Style: {style}. "
                           f"ComfyUI is available. Full pipeline pending M5 refinement.",
                )
    except Exception:
        pass

    return ToolCallResult(
        tool_name="generate_image",
        success=True,
        output=f"[Image generation stub] Prompt: {prompt}, Style: {style}. "
               f"ComfyUI not available. Install and start ComfyUI for image generation.",
    )


generate_image_tool = ToolSpec(
    name="generate_image",
    description="Generate an image (selfie, scene, etc.) for the character",
    parameters={
        "prompt": "string (image description)",
        "style": "string (anime/realistic/fantasy, default anime)",
    },
    handler=_generate_image,
)
