"""
The "real actions" tool system must stay wired into the prompt + reply parsing.

Regression lock: a model/prompt change must not silently drop (a) the tool
registry from the system prompt, or (b) the ```tool``` block parser. The model
emitting the call is the model's job; THIS guarantees the scaffolding is present.
"""
import json

from models.database import Character, Conversation
from services.chat_service import build_messages, _TOOL_CALL_RE


def _seed(db):
    char = Character(name="苏糖", description="d", system_prompt="s",
                     greeting="hi", category="Romance")
    db.add(char); db.commit(); db.refresh(char)
    conv = Conversation(character_id=char.id, intimacy_level=50)
    db.add(conv); db.commit(); db.refresh(conv)
    return char, conv


def test_action_tools_injected_into_prompt(db):
    char, conv = _seed(db)
    sys = "\n".join(m["content"] for m in build_messages(char, conv, db) if m["role"] == "system")
    assert "可用工具" in sys                 # the action section exists
    assert "```tool" in sys                  # the call format is taught
    # at least one real built-in tool is advertised
    assert any(t in sys for t in ("weather", "web_search", "schedule_message", "food_search"))


def test_generate_image_is_not_a_tool():
    # Photos go through the inline [IMG:] path (renders in chat). generate_image
    # must NOT also be a callable tool, or the model emits a raw ```tool``` block
    # that shows as text and never renders an image.
    from actions.registry import get_tool_registry
    schemas = get_tool_registry().get_schemas_text()
    assert "generate_image" not in schemas
    # the other real tools stay available
    assert "weather" in schemas and "web_search" in schemas


def test_tool_call_block_is_parsed():
    reply = '好的，我帮你查。\n```tool\n{"tool": "weather", "args": {"city": "上海"}}\n```\n稍等～'
    m = _TOOL_CALL_RE.search(reply)
    assert m is not None
    call = json.loads(m.group(1))
    assert call["tool"] == "weather" and call["args"]["city"] == "上海"
