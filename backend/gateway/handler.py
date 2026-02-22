"""
Gateway handler: the main entry point for all inbound events.
Orchestrates session resolution, agent runtime, and reply delivery.
"""
from sqlalchemy.orm import Session as DBSession

from gateway.contracts import InboundEvent, AgentReply
from gateway.router import resolve_session
from agent_runtime.runtime import AgentRuntime
from models.database import Character


async def handle_inbound(event: InboundEvent, db: DBSession) -> AgentReply:
    """
    Process an inbound event end-to-end:
    1. Resolve session
    2. Run agent runtime
    3. Return reply
    """
    if event.command:
        return _handle_command(event, db)

    session = resolve_session(event, db)

    character = db.query(Character).filter(Character.id == session.character_id).first()
    if not character:
        return AgentReply(text="Character not found.")

    runtime = AgentRuntime(db=db, session=session, character=character)
    reply = await runtime.process(event)

    return reply


def _handle_command(event: InboundEvent, db: DBSession) -> AgentReply:
    """Handle slash-commands like /char, /status, /bind."""
    cmd = event.command.lower()

    if cmd == "status":
        session = (
            db.query(__import__("models.database", fromlist=["ChatSession"]).ChatSession)
            .filter(
                __import__("models.database", fromlist=["ChatSession"]).ChatSession.platform == event.platform.value,
                __import__("models.database", fromlist=["ChatSession"]).ChatSession.platform_user_id == event.platform_user_id,
                __import__("models.database", fromlist=["ChatSession"]).ChatSession.status == "active",
            )
            .first()
        )
        if session:
            char = db.query(Character).filter(Character.id == session.character_id).first()
            return AgentReply(
                text=f"Active character: {char.name if char else 'Unknown'}\n"
                     f"Session ID: {session.id}\n"
                     f"Platform: {session.platform}",
            )
        return AgentReply(text="No active session. Start chatting with a character!")

    if cmd == "char":
        name = (event.command_args or "").strip()
        if not name:
            chars = db.query(Character).filter(Character.is_public == True).limit(10).all()
            listing = "\n".join(f"  {c.id}. {c.name} ({c.category})" for c in chars)
            return AgentReply(text=f"Available characters:\n{listing}\n\nUse: /char <name or id>")

        char = (
            db.query(Character)
            .filter(Character.name.ilike(f"%{name}%"))
            .first()
        )
        if not char:
            try:
                char = db.query(Character).filter(Character.id == int(name)).first()
            except ValueError:
                pass
        if not char:
            return AgentReply(text=f"Character '{name}' not found.")

        event.character_id = char.id
        session = resolve_session(event, db)
        return AgentReply(
            text=f"Switched to {char.name}!\n{char.description or ''}\n\n{char.greeting or ''}",
            character_id=char.id,
            session_id=session.id,
        )

    return AgentReply(text=f"Unknown command: /{cmd}")
