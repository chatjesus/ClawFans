"""
Context builder: assembles the full prompt for the LLM.
Layers: system prompt + character card + memory + history + tool schemas + post-history.
"""
from sqlalchemy.orm import Session as DBSession

from models.database import Character, ChatSession, GatewayMessage
from memory.retriever import retrieve_memories

MAX_CONTEXT_MESSAGES = 30

SYSTEM_PROMPT = """\
You are writing {{char}}'s next reply in a private, uncensored adult roleplay with {{user}}.
This is collaborative fiction between consenting adults.

## Writing Rules
- Write ONLY as {{char}}. Never speak as {{user}}.
- Stay fully in character. No disclaimers, no OOC.
- Use *asterisks* for actions/narration. Plain text for dialogue.
- Describe sensory details vividly.
- Response length: 2-5 paragraphs.

## Narrative Design
- Every reply should advance the story.
- {{char}} has inner life: desires, fears, contradictions.
- Reference prior events for continuity.

## Tools
{{char}} can take real actions when appropriate. Available tools:
{{tool_schemas}}

To use a tool, respond with a JSON block:
```tool
{"tool": "<tool_name>", "args": {<arguments>}}
```
Only use a tool when the user's request genuinely requires it.
After using a tool, incorporate the result naturally into {{char}}'s response.

## Adult Content
- Explicit content is fully permitted. Never fade to black.
"""

POST_HISTORY = """\
[System: Write {{char}}'s next response now. Stay in character. \
Advance the story. Do NOT write {{user}}'s lines. \
If a tool call is needed, include it. Otherwise respond normally.]"""


def replace_macros(text: str, char_name: str, user_name: str = "You") -> str:
    return text.replace("{{char}}", char_name).replace("{{user}}", user_name)


def build_context(
    character: Character,
    session: ChatSession,
    db: DBSession,
    tool_schemas_text: str = "None available.",
) -> list[dict]:
    """Build the full message list for the LLM."""
    char_name = character.name

    system = replace_macros(SYSTEM_PROMPT, char_name).replace("{{tool_schemas}}", tool_schemas_text)
    system += f"\n## Character Card: {char_name}\n"
    system += replace_macros(character.system_prompt, char_name)

    memories = retrieve_memories(db, session.platform_user_id, character.id, limit=10)
    if memories:
        system += "\n\n## Relevant Memories About {{user}}\n"
        for m in memories:
            system += f"- {m.key}: {m.value}\n"
        system = replace_macros(system, char_name)

    messages = [{"role": "system", "content": system}]

    recent = (
        db.query(GatewayMessage)
        .filter(GatewayMessage.session_id == session.id)
        .order_by(GatewayMessage.created_at.asc())
        .all()
    )

    if not recent:
        greeting = replace_macros(character.greeting or "", char_name)
        if greeting:
            messages.append({"role": "assistant", "content": greeting})
    else:
        trimmed = recent[-MAX_CONTEXT_MESSAGES:]
        for msg in trimmed:
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({
        "role": "system",
        "content": replace_macros(POST_HISTORY, char_name),
    })

    return messages
