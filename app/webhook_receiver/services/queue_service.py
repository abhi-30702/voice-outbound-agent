# app/webhook_receiver/services/queue_service.py
import asyncio
import logging
from uuid import UUID

import redis as sync_redis
from rq import Queue

logger = logging.getLogger(__name__)

POST_CALL_ANALYSIS_JOB = "app.post_call_analysis.worker.analyze_call"


def _enqueue_sync(redis_url: str, call_id: str) -> None:
    conn = sync_redis.from_url(redis_url)
    q = Queue(connection=conn)
    q.enqueue(POST_CALL_ANALYSIS_JOB, call_id=call_id)


async def enqueue_analysis(redis_url: str, call_id: UUID) -> None:
    try:
        await asyncio.to_thread(_enqueue_sync, redis_url, str(call_id))
        logger.info("Enqueued post_call_analysis job", extra={"call_id": call_id})
    except Exception as exc:
        logger.error(
            "Failed to enqueue post_call_analysis job",
            extra={"call_id": call_id, "error": str(exc)},
        )
