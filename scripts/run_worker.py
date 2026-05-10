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
    config = DialerConfig(retell_api_key=os.environ["RETELL_API_KEY"])
    worker = DialerWorker(config)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
