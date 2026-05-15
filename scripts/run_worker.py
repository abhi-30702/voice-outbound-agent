import asyncio
import logging
import os

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


async def main() -> None:
    config = DialerConfig(
        livekit_url=os.environ["LIVEKIT_URL"],
        livekit_api_key=os.environ["LIVEKIT_API_KEY"],
        livekit_api_secret=os.environ["LIVEKIT_API_SECRET"],
        livekit_sip_trunk_id=os.environ["LIVEKIT_SIP_TRUNK_ID"],
    )
    worker = DialerWorker(config)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
