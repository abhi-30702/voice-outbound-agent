# app/webhook_receiver/main.py
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from app.core.settings import settings
from app.db.session import close_db, init_session_factory
from app.dashboard_api.router import api_router, ws_router
from app.webhook_receiver.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory = await init_session_factory()
    app.state.session_factory = session_factory
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await close_db()
    await app.state.redis.aclose()


app = FastAPI(title="Retell Webhook Receiver", lifespan=lifespan)
app.include_router(router)
app.include_router(api_router)
app.include_router(ws_router)
