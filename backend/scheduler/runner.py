"""
Scheduler runner: periodically checks for due jobs and executes them.
Will be connected to the gateway for message delivery in M7.
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

    if job.job_type == "send_message":
        # Will be implemented in M7: route through gateway to deliver message
        logger.info(
            f"[STUB] Would send message to user {job.user_id} "
            f"on {job.platform}: {payload.get('text', '')}"
        )
    elif job.job_type == "morning_greeting":
        logger.info(f"[STUB] Morning greeting for user {job.user_id}")
    else:
        logger.warning(f"Unknown job type: {job.job_type}")


async def scheduler_loop(interval_seconds: int = 30):
    """Background loop that checks for due jobs periodically."""
    logger.info(f"Scheduler started (interval: {interval_seconds}s)")
    while True:
        try:
            await check_due_jobs()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(interval_seconds)
