# app/webhook_receiver/services/queue_service.py
import asyncio
import logging
from uuid import UUID

import redis as sync_redis
from rq import Queue, Retry

logger = logging.getLogger(__name__)

POST_CALL_ANALYSIS_JOB = "app.post_call_analysis.worker.analyze_call"


def _enqueue_sync(redis_url: str, call_id: str) -> None:
    conn = sync_redis.from_url(redis_url)
    try:
        q = Queue(connection=conn)
        q.enqueue(
            POST_CALL_ANALYSIS_JOB,
            call_id=call_id,
            retry=Retry(max=3, interval=[60, 120, 300]),
        )
    finally:
        conn.close()


async def enqueue_analysis(redis_url: str, call_id: UUID) -> None:
    try:
        await asyncio.to_thread(_enqueue_sync, redis_url, str(call_id))
        logger.info("enqueued post_call_analysis job", extra={"call_id": str(call_id)})
    except Exception as exc:
        logger.error(
            "failed to enqueue post_call_analysis job",
            extra={"call_id": str(call_id), "error": str(exc)},
        )
