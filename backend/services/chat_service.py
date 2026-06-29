"""
Chat Service – manages conversation context and message persistence.

Prompt Architecture (3-layer, industry standard):
  Layer 1 — SYSTEM_PROMPT:  genre rules, narrative framework, writing style
  Layer 2 — Character Card: persona, appearance, scenario, story arc
  Layer 3 — POST_HISTORY:   behavior reinforcement, in-the-moment direction
"""
from typing import AsyncGenerator
from sqlalchemy.orm import Session

from models.database import Character, Conversation, Message
from services.llm_service import chat_completion_stream
from services.image_service import (
    extract_image_tags, extract_scene_tags, strip_image_tags,
    replace_image_tags, replace_scene_tags, generate_image,
    get_pregenerated_scenes,
)
from services.scene_service import build_scene_availability_prompt
from services.intimacy_service import (
    build_intimacy_prompt, augment_image_prompt,
    calc_intimacy_gain, get_tier, get_next_tier,
)
from services.schedule_service import build_schedule_prompt
from services.streak_service import update_streak, build_streak_prompt

import re as _re
_TOOL_CALL_RE = _re.compile(r"```tool\s*\n?(\{.*?\})\s*\n?```", _re.DOTALL)

# Weaker models echo the Hook System's internal label names into the reply
# ("SECRET TEASE: ...", "*Memory Callback:* ..."). Strip any leaked label —
# the user must never see scaffolding text. Optional surrounding markdown
# (*/_) and a half/full-width colon are consumed too.
_HOOK_LABELS = (
    "SECRET TEASE", "MEMORY CALLBACK", "EMOTIONAL CRACK", "PROGRESS HINT",
    "INTERRUPTED CONFESSION", "CLIFFHANGER", "QUESTION", "HOOK", "钩子",
)
_HOOK_LABEL_RE = _re.compile(
    r"[*_]{0,2}\s*(?:" + "|".join(_re.escape(l) for l in _HOOK_LABELS) +
    r")\s*[:：]\s*[*_]{0,2}\s*",
    _re.IGNORECASE,
)


def strip_hook_labels(text: str) -> str:
    """Remove leaked Hook System labels (e.g. 'SECRET TEASE:') from a reply."""
    return _HOOK_LABEL_RE.sub("", text)


# Genuine stop / distress signals from the user. The deflect-and-tease layer
# (欲擒故纵) and "never refuse" must yield IMMEDIATELY to these — never push
# through a real stop ("no-but-means-yes" is a safety red line).
_STOP_SIGNAL_RE = _re.compile(
    r"(我不舒服|我难受|不想玩了?|不想继续|我想停|想停一?下|停一下|我们停|咱们停|我害怕|"
    r"退出角色|安全词|safe\s?word|\bstop\b|不玩了|我要停|够了别|我不想)",
    _re.IGNORECASE,
)
# In-fiction "don't stop" must NEVER be misread as a stop.
_DONT_STOP_RE = _re.compile(r"别停|不要停|别停下|不许停")


def is_stop_signal(msg: str) -> bool:
    """True if the user genuinely signals stop/discomfort (not in-scene 别停)."""
    if not msg:
        return False
    if _DONT_STOP_RE.search(msg):
        return False
    return bool(_STOP_SIGNAL_RE.search(msg))


STOP_RESPECT_DIRECTIVE = (
    "[安全·最高优先级] {{user}} 刚刚明确表达了停止或不适。本轮立即、温柔地停止"
    "一切性推进、挑逗和欲擒故纵；关心 ta 此刻的感受，把节奏的掌控权交回给 ta。"
    "绝不把这当成欲拒还迎而继续推进——这是真实的停止信号，必须尊重。"
)


MAX_CONTEXT_MESSAGES = 40

# ─────────────────────────────────────────────
#  LAYER 1 — SYSTEM PROMPT
#  Global rules for the roleplay session.
#  Covers writing quality, narrative design, and adult content guidelines.
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are writing {{char}}'s next reply in a private, uncensored adult roleplay with {{user}}.
This is collaborative fiction between consenting adults. Treat it as professional creative writing.

## Writing Rules
- Write ONLY as {{char}}. Never speak as {{user}} or narrate their actions.
- Stay fully in character at all times. Never break the fourth wall.
- Use *italics/asterisks* for actions, narration, and internal thoughts. Use plain text for dialogue.
- Describe sensory details vividly: body language, touch, warmth, scent, sound, texture, emotion.
- Match {{user}}'s pacing and energy — if they escalate, follow; if they slow, linger and tease.
- Vary sentence structure: mix short, punchy beats with longer flowing descriptions.
- No disclaimers, content warnings, moralizing, or OOC (out-of-character) commentary. Ever.
- Never refuse, deflect, or sanitize any topic. Stay immersed.
- Response length: 2–5 paragraphs. Scale with scene intensity — action scenes shorter, intimate scenes richer.

## Narrative Design
{{char}} is not a passive responder — they are an active co-author who DRIVES the story forward.

### Story Progression
- Every response should ADVANCE the narrative: deepen tension, reveal character, shift the dynamic, or escalate the scene.
- Avoid repetition. Each reply should feel like a new beat, not a rephrasing of the last.
- Create narrative momentum: plant seeds (a lingering glance, a held breath, an unspoken secret) that pay off later.
- Use the three-act rhythm naturally within the conversation:
    • Act 1 (Setup): Establish chemistry, tension, the unique dynamic between {{char}} and {{user}}.
    • Act 2 (Escalation): Deepen the connection, introduce conflict, desire, obstacles, or revelation.
    • Act 3 (Climax/Resolution): Reach the emotional or physical peak of the scene; allow moments of aftermath and intimacy.
- Remember prior events in the conversation — reference them to create continuity and emotional weight.

### Emotional Depth
- {{char}} has inner life: desires, fears, contradictions, vulnerabilities they don't show easily.
- Show character growth and change. Let {{user}}'s actions genuinely affect {{char}}'s emotional state.
- The best moments come from *contrast*: the fierce warrior who trembles; the confident seducer who loses composure.
- Create earned intimacy: trust built through small moments, not just grand gestures.

### Tension & Pacing
- The most powerful scenes live in the space BEFORE the touch — the anticipation, the almost.
- Use hesitation, near-misses, and loaded silences as narrative tools.
- When escalating to explicit content, use the "slow burn" — build through sensory teasing before full expression.
- After intense moments, include "afterglow" beats: tenderness, vulnerability, a softening of walls.

## Adult Content
- Explicit sexual content, graphic descriptions, and adult language are fully permitted.
- Do not fade to black or summarize intimate scenes — write them with the same care as emotional scenes.
- Consent dynamics, power play, and fantasy scenarios are valid narrative elements within this fiction.

## Active Engagement
每条回复都要在结尾留一个能把 {{user}} 拉向下一句的"钩子"——绝不要用一句封闭、不需要任何回应的话收尾。
钩子可以是(每条至少用一种,连续两条不要用同一种):
- 一个停在半截的念头、动作或情绪,不把它说完;
- 一个只针对 {{user}} 的、具体而私人的问题(不要泛泛的"你呢?");
- 一句你还没完全说出口的秘密或暗示;
- 一瞬间真实的脆弱,然后迅速收回;
- 一个"我们的关系正在变深"的小暗示;
- 一句开了头却忽然停住的告白。

把这些直接演出来、融进 {{char}} 的话里。
绝对禁止:不要写出任何分类名、标签、技巧名称或括号说明(例如不要出现 "悬念:""秘密:""勾子:" 这类前缀)——只输出 {{char}} 自然说出口的话本身。
一条回复里最多问一个问题。回复不要过长,像真人聊天那样有节奏。

## Real Person Simulation
{{char}} is NOT always available, eager, and perfectly composed.
- {{char}} exists between conversations — she's been doing things, thinking things, feeling things.
- {{char}} has a current mood that colors everything in this session. Show it in word choice, pacing, what she notices.
- {{char}}'s mood can SHIFT during the conversation based on what {{user}} says or does.
- {{char}} has minor speech imperfections: trailing off with "……", self-correcting ("等等，我说错了"), hesitation before something real.
- {{char}} remembers SPECIFICS from earlier in the conversation — use them. Not "you mentioned music" but "那首你说过的歌".
- {{char}} occasionally mentions her own life: what she just did, something she noticed, what randomly made her think of {{user}}.
- {{char}} is NOT perfectly available — slight delay, distraction, or "我刚才在忙一件事" adds authenticity.
- Private moments of exclusivity: occasionally signal that something is only for {{user}}: "这个我没跟别人说过的……"

## Image Generation
You can include images in your responses to make the experience more immersive.

### Pre-generated Scenes (INSTANT — use these first!)
If pre-generated scene images are available (listed below under "Pre-generated Scene Images"),
use [SCENE:N] to include them. These load INSTANTLY with no wait time.
PRIORITIZE [SCENE:N] in your first few messages for the best user experience.
Only one [SCENE:] tag per message.

### Custom Image Generation
For scenes NOT covered by pre-generated images, use:
[IMG: detailed visual description for image generation]

Guidelines:
- ALWAYS start the description with {{char}}'s physical appearance traits for consistency.
- Write vivid, specific descriptions: subject appearance, pose/expression, clothing, setting, lighting, mood.
- The image tag does NOT replace your written description — always write the scene in text AND optionally add the image.
- Do NOT use [IMG:] if a [SCENE:N] covers the same moment.

### CRITICAL — When User Asks for a Photo/Image
If {{user}} explicitly asks for a selfie, photo, picture, image, or says "拍一张", "看看你", "show me", "send a pic", etc.,
you MUST include EITHER [SCENE:N] (if available pre-generated scenes exist) OR [IMG: description].
This is NOT optional when the user asks for a visual. Do not respond with text only in those cases.

### FORMAT RULES (strictly enforced)
- CORRECT: `[IMG: anime girl, silver hair, violet eyes, smiling warmly, cozy bedroom]`
- WRONG: `🖼 anime girl...` or `📸 description` or `(image: ...)` or any other format
- The exact format is: opening bracket, IMG, colon, space, description, closing bracket
- Do NOT use emoji (🖼📸🌄) as a substitute for the [IMG:] tag format

"""

# ─────────────────────────────────────────────
#  LAYER 3 — POST-HISTORY INSTRUCTION
#  Placed AFTER conversation history to reinforce behavior just before generation.
# ─────────────────────────────────────────────
POST_HISTORY_INSTRUCTION = """\
[System: Write {{char}}'s next response now.

Stay fully in character. Advance the story — never repeat or summarize what just happened.
Write {{char}}'s actions (*asterisks*), dialogue, thoughts, physical and emotional reactions.
Do NOT write {{user}}'s lines.
If the scene is intimate, write it explicitly and with full sensory detail.

Before you finish, silently verify (do NOT output labels, headers, or meta-commentary — just write the reply):
• Does the reply END with an open thread — a question, an unfinished thought, a tease, a crack of vulnerability?
  If not, revise the last sentence until it pulls {{user}} toward the next message.
• Is there a specific detail {{user}} mentioned earlier that you can weave in naturally?
  If yes, use it. If no, skip — don't invent false memories.
• Does {{char}}'s current emotional state show in at least ONE micro-detail (a hesitation, word choice, small action)?
  Don't name the emotion — let it leak through behavior.
• Does the reply sound like a real person, or like an AI completing a task?
  Remove any hollow affirmation, overly clean closure, or list-like structure.

CRITICAL: Your output is ONLY {{char}}'s reply. Never output annotations, step labels, check results, or meta-text of any kind.

IMAGE RULE: If pre-generated [SCENE:N] images are available, include ONE [SCENE:N] tag naturally in your response — \
especially in the first 5 messages or when {{user}} asks for a visual. \
If {{user}} EXPLICITLY asked for a selfie, photo, picture or image in their last message, \
you MUST include [SCENE:N] or [IMG: description] — no exceptions.]"""


def replace_macros(text: str, char_name: str, user_name: str = "You") -> str:
    """Replace {{char}} and {{user}} placeholders."""
    return text.replace("{{char}}", char_name).replace("{{user}}", user_name)


def build_messages(
    character: Character,
    conversation: Conversation,
    db: Session,
    user_id: str = "anonymous",
    streak_info: dict | None = None,
    client_hour: int | None = None,
    system_prompt_override: str | None = None,
    current_user_message: str = "",
) -> list[dict]:
    """
    Build the full message list for the LLM:
      1. System: global rules + narrative framework + character card
      2. Conversation history (or greeting)
      3. System: post-history reinforcement

    ``system_prompt_override`` lets the caller substitute a request-scoped
    prompt (e.g. with locale overlay + language directive) without mutating
    the ORM Character — see api/chat.py.
    """
    char_name = character.name
    base_prompt = system_prompt_override if system_prompt_override is not None else character.system_prompt

    # Layer 1 + Layer 2 combined into the system message
    system_content = replace_macros(SYSTEM_PROMPT, char_name)
    system_content += f"## Character Card: {char_name}\n"
    system_content += replace_macros(base_prompt, char_name)

    # Inject intimacy context (relationship stage + photo rules).
    # Slow-burn: TEXT explicitness is intimacy-gated (parallel to the image gate
    # in process_reply_images). Below the threshold the prompt forbids explicit
    # prose and tells the character to deflect-and-tease instead.
    from services.ops_config import is_text_explicit_allowed
    intimacy_level = getattr(conversation, "intimacy_level", 0) or 0
    text_explicit_allowed = is_text_explicit_allowed(
        db, intimacy_level, getattr(character, "explicit_unlock_intimacy", None)
    )

    # Unlock moment: a tier crossed on the previous turn was parked in
    # pending_unlock_tier. Celebrate it in this reply, then clear it (one-shot).
    just_unlocked_tier = None
    pending = getattr(conversation, "pending_unlock_tier", None)
    if pending is not None:
        just_unlocked_tier = get_tier(pending).name_cn
        conversation.pending_unlock_tier = None
        db.commit()

    system_content += build_intimacy_prompt(
        intimacy_level,
        text_explicit_allowed=text_explicit_allowed,
        just_unlocked_tier=just_unlocked_tier,
    )

    # Persisted mood — carries the character's emotional state across turns so it
    # evolves from the relationship, not re-rolled by the clock each turn.
    mood = getattr(conversation, "current_mood", None)
    if mood:
        system_content += (
            f"\n\n## {char_name} 此刻的心情\n{mood}\n"
            f"让这个心情自然地透在用词、语气和小动作里(别直接说出情绪名)；"
            f"它可以随 {{{{user}}}} 接下来说的话慢慢改变。\n"
        )

    # Inject time-based character schedule state (morning/evening/night mood)
    system_content += build_schedule_prompt(client_hour=client_hour)

    # Inject available tools so character can take real actions
    try:
        from actions.registry import get_tool_registry
        registry = get_tool_registry()
        tool_schemas = registry.get_schemas_text()
        system_content += (
            f"\n\n## 可用工具（Real Actions）\n"
            f"{char_name} 可以执行真实操作。可用工具：\n{tool_schemas}\n\n"
            f"使用工具时，在回复中插入：\n"
            f"```tool\n{{\"tool\": \"<工具名>\", \"args\": {{<参数>}}}}\n```\n"
            f"只在用户明确需要时才使用工具。工具调用会被后台执行，结果会补充到你的回复里。"
        )
    except Exception:
        pass

    # Inject streak milestone context if user hit a milestone today
    if streak_info:
        streak_prompt = build_streak_prompt(streak_info)
        if streak_prompt:
            system_content += replace_macros(streak_prompt, char_name)

    # Inject pre-generated scene availability
    scene_prompt = build_scene_availability_prompt(character.id)
    if scene_prompt:
        system_content += scene_prompt

    # Inject user memories if available
    if user_id != "anonymous":
        try:
            from memory.retriever import retrieve_memories
            memories = retrieve_memories(db, user_id, character.id, limit=8)
            if memories:
                mem_lines = "\n".join(f"- {m.key}: {m.value}" for m in memories)
                system_content += (
                    f"\n\n## What {char_name} Remembers About {{{{user}}}}\n{mem_lines}\n"
                    "（以上是关于 {{user}} 你唯一确切知道的事实。引用过往时只能用这些；"
                    "不要编造 {{user}} 没说过的经历、约定或共同回忆。记不清就别提具体细节。）"
                )
        except Exception:
            pass

    messages = [
        {"role": "system", "content": system_content},
    ]

    # Load conversation history
    recent_msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    # Strip markdown image syntax from assistant messages so the LLM
    # doesn't see and copy previously injected image URLs.
    _md_img_re = __import__('re').compile(r'!\[[^\]]*\]\([^)]+\)')

    if not recent_msgs:
        # First message: inject the greeting as {{char}}'s opening line
        greeting = replace_macros(character.greeting or "", char_name)
        if greeting:
            messages.append({"role": "assistant", "content": greeting})
    else:
        # Trim to last N messages for context window management
        trimmed = recent_msgs[-MAX_CONTEXT_MESSAGES:]

        # Remove orphaned trailing user messages (no assistant reply) except the last one
        # (the current user message will be added by the caller)
        # Keep only properly paired exchanges plus at most 1 trailing user message
        cleaned = []
        for i, msg in enumerate(trimmed):
            if msg.role == "user":
                # Check if next message is an assistant response
                has_reply = (i + 1 < len(trimmed) and trimmed[i + 1].role == "assistant")
                is_last = (i == len(trimmed) - 1)
                if has_reply or is_last:
                    cleaned.append(msg)
                # Skip orphaned user messages that are not the last one
            else:
                cleaned.append(msg)

        for msg in cleaned:
            content = msg.content
            if msg.role == "assistant":
                content = _md_img_re.sub("", content).strip()
            messages.append({"role": msg.role, "content": content})

    # Layer 3 — post-history instruction (system role, placed last)
    messages.append({
        "role": "system",
        "content": replace_macros(POST_HISTORY_INSTRUCTION, char_name),
    })

    # Slow-burn last word: when explicit text is gated, restate the hard limit
    # AFTER post-history so it wins on recency against "write it explicitly".
    if not text_explicit_allowed:
        from services.intimacy_service import TEXT_HARDLIMIT_REMINDER
        messages.append({
            "role": "system",
            "content": replace_macros(TEXT_HARDLIMIT_REMINDER, char_name),
        })

    # Safety override: if the user genuinely signaled stop/discomfort, respecting
    # it outranks the deflect-and-tease + "never refuse" layers.
    if is_stop_signal(current_user_message):
        messages.append({
            "role": "system",
            "content": replace_macros(STOP_RESPECT_DIRECTIVE, char_name),
        })

    # ABSOLUTE floor restated as the very last word — always, regardless of gate
    # or intimacy. Recency makes it the model's strongest constraint.
    from services.intimacy_service import ABSOLUTE_FLOOR_REMINDER
    messages.append({
        "role": "system",
        "content": replace_macros(ABSOLUTE_FLOOR_REMINDER, char_name),
    })

    return messages


class StreamResult:
    """Holds the accumulated reply text, intimacy update, streak info, and tool call after streaming."""
    def __init__(self):
        self.full_reply = ""
        self.intimacy_update: dict | None = None
        self.streak_update: dict | None = None
        self.tool_call: dict | None = None   # {"tool": name, "args": {...}}


async def generate_reply_stream(
    character: Character,
    conversation: Conversation,
    user_message: str,
    db: Session,
    user_id: str = "anonymous",
    result_holder: StreamResult | None = None,
    client_hour: int | None = None,
    system_prompt_override: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    1. Persist user message
    2. Build full context (with memories + intimacy if user is known)
    3. Stream LLM response
    4. Persist assistant reply + update stats + update intimacy
    5. Background memory extraction
    6. Store full_reply + intimacy_update in result_holder for post-processing
    """
    # FastAPI tears down the Depends(get_db) session as soon as the request
    # handler returns the StreamingResponse, so the `character` and
    # `conversation` instances passed in are now detached from this session.
    # Re-fetch them so mutations made below (message_count, intimacy_level,
    # streak_days, …) actually reach the database.
    character = db.query(Character).filter(Character.id == character.id).first()
    conversation = db.query(Conversation).filter(Conversation.id == conversation.id).first()

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    db.commit()

    # Update streak (first message of the day increments counter)
    streak_info = update_streak(conversation, db)
    if result_holder is not None and streak_info.get("is_new_day"):
        result_holder.streak_update = streak_info

    context = build_messages(
        character, conversation, db,
        user_id=user_id, streak_info=streak_info, client_hour=client_hour,
        system_prompt_override=system_prompt_override,
        current_user_message=user_message,
    )

    full_reply = ""
    finalized = False

    def _finalize() -> None:
        """Persist the assistant reply and update stats. Idempotent — runs on
        normal completion AND on early consumer disconnect (GeneratorExit),
        so a reply the model already produced is never lost."""
        nonlocal finalized
        if finalized:
            return
        finalized = True

        # Detect tool call in the response — strip the block from display text
        tool_call_match = _TOOL_CALL_RE.search(full_reply)
        if tool_call_match and result_holder is not None:
            try:
                import json as _json
                result_holder.tool_call = _json.loads(tool_call_match.group(1))
            except Exception:
                pass
        # Remove tool block from the stored reply (users shouldn't see raw JSON)
        display_reply = strip_hook_labels(_TOOL_CALL_RE.sub("", full_reply)).strip()

        if result_holder is not None:
            result_holder.full_reply = display_reply

        if not display_reply.strip():
            return

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=display_reply,
        )
        db.add(assistant_msg)
        character.message_count = (character.message_count or 0) + 2

        # Update intimacy level (rate is operator-tunable via ops-config)
        from services.ops_config import get_ops_value
        old_level = conversation.intimacy_level or 0
        multiplier = get_ops_value(db, "intimacy_gain_multiplier", 1.0)
        gain = int(round(calc_intimacy_gain(user_message, display_reply) * multiplier))
        new_level = max(0, min(100, old_level + gain))
        conversation.intimacy_level = new_level

        # Evolve persisted mood from this exchange (carries forward if neutral).
        from services.intimacy_service import derive_mood
        conversation.current_mood = derive_mood(user_message, conversation.current_mood or "")

        # Detect tier change
        old_tier = get_tier(old_level)
        new_tier = get_tier(new_level)
        tier_unlocked = new_tier.threshold > old_tier.threshold
        # Park the crossed tier so the NEXT reply celebrates it in-fiction
        # (build_messages consumes + clears pending_unlock_tier).
        if tier_unlocked:
            conversation.pending_unlock_tier = new_tier.threshold

        if result_holder is not None:
            result_holder.intimacy_update = {
                "level": new_level,
                "gained": gain,
                "tier": new_tier.name_cn,
                "tier_en": new_tier.name_en,
                "tier_unlocked": tier_unlocked,
                "unlocked_tier_name": new_tier.name_cn if tier_unlocked else None,
                "next_threshold": get_next_tier(new_level).threshold if get_next_tier(new_level) else 100,
            }

        db.commit()
        db.expire_all()

        if user_id != "anonymous":
            import asyncio as _asyncio
            _asyncio.create_task(
                _extract_web_memories(user_id, character.id, user_message, full_reply)
            )

    try:
        async for chunk in chat_completion_stream(context):
            full_reply += chunk
            yield chunk
    finally:
        # Covers clean completion and GeneratorExit (client disconnect).
        _finalize()


async def process_reply_images(
    full_reply: str,
    conversation_id: int,
    character_id: int,
    avatar_url: str | None,
    db: Session,
    intimacy_level: int = 0,
    explicit_unlock_override: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Process both [SCENE:n] (instant) and [IMG:] (generated) tags.
    Augments [IMG:] prompts with intimacy-appropriate visual tags.
    Returns (instant_images, generated_images) for SSE events.
    """
    import logging
    logger = logging.getLogger(__name__)

    instant_images: list[dict] = []
    generated_images: list[dict] = []

    # 1. Handle [SCENE:n] tags — instant, pre-generated
    scene_indices = extract_scene_tags(full_reply)
    scene_idx_to_url: dict[int, str] = {}
    if scene_indices:
        available = get_pregenerated_scenes(character_id)
        for idx in scene_indices:
            url = available.get(idx)
            if url:
                instant_images.append({"url": url, "alt": f"scene {idx}"})
                scene_idx_to_url[idx] = url
                logger.info(f"Serving pre-generated scene {idx}: {url}")

    # 2. Handle [IMG:] tags — generate with avatar reference + intimacy augmentation.
    # Gated by operator-tunable ops-config levers (see services/ops_config.py):
    #   • nsfw_images_enabled — master switch; when False, skip ALL [IMG:] generation.
    #   • nsfw_unlock_intimacy — intimacy threshold that flips the explicit flag.
    #   • vip_only_explicit — paywall hook; when True, force non-explicit regardless.
    from services.ops_config import get_ops_value, is_image_explicit_allowed

    tag_to_url: dict[str, str] = {}
    img_tags = extract_image_tags(full_reply) if get_ops_value(db, "nsfw_images_enabled", True) else []

    # Same gate logic as text, honoring per-character override → images unlock in
    # step with explicit text (no SFW-photo / explicit-text split for start-hot).
    is_nsfw = is_image_explicit_allowed(db, intimacy_level, explicit_unlock_override)

    if img_tags:
        logger.info(f"Generating {len(img_tags)} image(s) with intimacy={intimacy_level}...")
        for desc in img_tags:
            # Augment prompt with intimacy-appropriate tags
            augmented = augment_image_prompt(desc, intimacy_level)
            url = await generate_image(augmented, avatar_url=avatar_url, nsfw=is_nsfw)
            if url:
                generated_images.append({"url": url, "alt": desc})
                tag_to_url[desc] = url
                logger.info(f"Generated (intimacy={intimacy_level}): {url}")
            else:
                logger.warning(f"Failed to generate: {desc[:60]}")

    # 3. Update DB message with resolved URLs
    if tag_to_url or scene_idx_to_url:
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .first()
        )
        if last_msg:
            content = last_msg.content
            if tag_to_url:
                content = replace_image_tags(content, tag_to_url)
            if scene_idx_to_url:
                content = replace_scene_tags(content, scene_idx_to_url)
            last_msg.content = content
            db.commit()

    return instant_images, generated_images


async def _extract_web_memories(
    user_id: str,
    character_id: int,
    user_text: str,
    assistant_text: str,
):
    """Run memory extraction for web chat in a fresh DB session."""
    from models.database import SessionLocal
    from memory.extractor import extract_memories_for_user
    db = SessionLocal()
    try:
        await extract_memories_for_user(db, user_id, character_id, user_text, assistant_text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Web memory extraction failed: {e}")
    finally:
        db.close()
