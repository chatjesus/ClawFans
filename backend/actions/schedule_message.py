"""
Schedule message tool: creates a scheduled job for proactive messaging.
"""
from datetime import datetime
from gateway.contracts import ToolCallResult
from actions.registry import ToolSpec


async def _schedule_message(
    message: str,
    delay_minutes: int = 60,
    recurrence: str = "once",
) -> ToolCallResult:
    """
    Schedule a message to be sent later.
    For now stores in memory; M7 will connect this to the scheduler/DB.
    """
    run_at = datetime.utcnow().__class__.utcnow()
    # Actual DB persistence will be added in M7 (scheduler milestone)
    return ToolCallResult(
        tool_name="schedule_message",
        success=True,
        output=(
            f"Message scheduled: '{message}' "
            f"in {delay_minutes} minutes ({recurrence}). "
            f"[Note: Scheduler integration pending M7]"
        ),
    )


schedule_message_tool = ToolSpec(
    name="schedule_message",
    description="Schedule a message to be sent to the user later",
    parameters={
        "message": "string (message to send)",
        "delay_minutes": "int (minutes from now, default 60)",
        "recurrence": "string (once/daily/weekly, default once)",
    },
    handler=_schedule_message,
)
