"""
Scheduler runner: periodically checks for due jobs and executes them.
Handles proactive message delivery via Telegram.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session as DBSession
from models.database import ScheduledJob, SessionLocal

logger = logging.getLogger(__name__)


async def check_due_jobs():
    """Check for and execute due scheduled jobs."""
    db: DBSession = SessionLocal()
    try:
        now = datetime.utcnow()
        due_jobs = (
            db.query(ScheduledJob)
            .filter(
                ScheduledJob.run_at <= now,
                ScheduledJob.status == "pending",
            )
            .limit(20)
            .all()
        )

        for job in due_jobs:
            try:
                job.status = "running"
                job.attempts += 1
                db.commit()

                await _execute_job(job, db)

                job.status = "completed"
                db.commit()
                logger.info(f"Job {job.id} completed ({job.job_type})")

            except Exception as e:
                logger.error(f"Job {job.id} failed: {e}")
                job.status = "failed" if job.attempts >= 3 else "pending"
                db.commit()

    finally:
        db.close()


async def _execute_job(job: ScheduledJob, db: DBSession):
    """Execute a single scheduled job. Routes by job_type."""
    import json
    payload = json.loads(job.payload_json) if job.payload_json else {}

    if job.job_type == "proactive_message":
        await _send_proactive(job, payload)

    elif job.job_type == "send_message":
        # Generic send: route by platform
        if job.platform == "telegram":
            chat_id = payload.get("chat_id") or job.user_id
            text = payload.get("text", "")
            await _send_telegram(chat_id, text)
        else:
            logger.info(
                f"[send_message] platform={job.platform} "
                f"user={job.user_id}: {payload.get('text', '')}"
            )

    elif job.job_type == "morning_greeting":
        logger.info(f"[STUB] Morning greeting for user {job.user_id}")

    else:
        logger.warning(f"Unknown job type: {job.job_type}")


async def _send_proactive(job: ScheduledJob, payload: dict):
    """Send a proactive character message via Telegram."""
    chat_id = payload.get("chat_id")
    text = payload.get("text", "")
    char_name = payload.get("char_name", "")

    if not chat_id or not text:
        logger.warning(f"Proactive job {job.id} missing chat_id or text")
        return

    success = await _send_telegram(chat_id, text)
    if success:
        logger.info(
            f"[Proactive] {char_name} → chat_id={chat_id}: {text[:60]}..."
        )
    else:
        raise RuntimeError(f"Telegram send failed for chat_id={chat_id}")


async def _send_telegram(chat_id: str, text: str) -> bool:
    """Send a message via the Telegram bot."""
    try:
        from channels.telegram.adapter import send_proactive_message
        return await send_proactive_message(str(chat_id), text)
    except Exception as e:
        logger.error(f"_send_telegram error: {e}")
        return False


async def scheduler_loop(interval_seconds: int = 30):
    """Background loop that checks for due jobs and scans for proactive messages."""
    logger.info(f"Scheduler started (interval: {interval_seconds}s)")
    # Proactive scanners run every 5 minutes (not every 30s tick)
    _proactive_tick = 0
    _proactive_every = max(1, 300 // interval_seconds)  # ~5 min

    while True:
        try:
            await check_due_jobs()

            _proactive_tick += 1
            if _proactive_tick >= _proactive_every:
                _proactive_tick = 0
                try:
                    from services.proactive_service import schedule_proactive_jobs
                    count = await schedule_proactive_jobs()
                    if count:
                        logger.info(f"[Proactive] Scheduled {count} new proactive job(s)")
                except Exception as pe:
                    logger.error(f"Proactive scan error: {pe}")

                # Web proactive recall: stage "missed you" messages for quiet
                # web conversations (Telegram is handled above).
                try:
                    from services.web_proactive import stage_web_proactive_messages
                    web_count = await stage_web_proactive_messages()
                    if web_count:
                        logger.info(f"[WebProactive] Staged {web_count} message(s)")
                except Exception as we:
                    logger.error(f"Web proactive scan error: {we}")

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(interval_seconds)
