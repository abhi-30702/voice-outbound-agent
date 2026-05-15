"""Entry point to start the LiveKit Agent worker process.

Usage:
    python scripts/run_agent.py start
    python scripts/run_agent.py dev      # development mode with auto-reload
    python scripts/run_agent.py connect  # connect to a specific room
"""

import logging

from livekit.agents import WorkerOptions, cli

from app.livekit_agent.agent import entrypoint
from app.livekit_agent.config import agent_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=agent_settings.LIVEKIT_API_KEY,
            api_secret=agent_settings.LIVEKIT_API_SECRET,
            ws_url=agent_settings.LIVEKIT_URL,
        )
    )
