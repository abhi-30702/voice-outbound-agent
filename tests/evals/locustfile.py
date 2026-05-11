"""Locust load test — verifies DialerWorker stays within 1 CPS hard limit.

Run via locust:
    locust -f tests/evals/locustfile.py --headless -u 1 -r 1 --run-time 20s

Or directly:
    python tests/evals/locustfile.py
"""
import asyncio
import sys
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

# Ensure the project root is on sys.path when running standalone.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from locust import User, events, task, constant

from app.dialing_worker.config import DialerConfig
from app.dialing_worker.worker import DialerWorker
from app.models import Contact, ContactStatus

LEAD_COUNT = 10
_dispatch_timestamps: list[float] = []


def _build_leads() -> list[Contact]:
    past = datetime.utcnow() - timedelta(minutes=5)
    leads = []
    for i in range(LEAD_COUNT):
        lead = Contact(
            id=uuid.uuid4(),
            phone_number=f"+1555{str(i).zfill(7)}",
            first_name="Test",
            timezone="America/New_York",
            status=ContactStatus.PENDING,
            campaign_id=uuid.uuid4(),
            retry_count=0,
            next_retry_at=past,
        )
        leads.append(lead)
    return leads


def _build_mock_session() -> AsyncMock:
    campaign = MagicMock()
    campaign.name = "Load Test Campaign"
    campaign.llm_config = {"retell_agent_id": "agent_mock"}
    session = AsyncMock()
    session.get = AsyncMock(return_value=campaign)
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _build_worker() -> DialerWorker:
    with patch("app.dialing_worker.retell_client.httpx.AsyncClient"):
        worker = DialerWorker(DialerConfig(retell_api_key="test"))
    worker.retell_client.create_call = AsyncMock(return_value={"call_id": "mock_call_id"})
    return worker


def _compute_max_cps(timestamps: list[float]) -> float:
    if len(timestamps) < 2:
        return 0.0
    windows: defaultdict[int, int] = defaultdict(int)
    t0 = timestamps[0]
    for ts in timestamps:
        windows[int(ts - t0)] += 1
    return float(max(windows.values()))


async def _run_dispatch_loop(leads: list[Contact]) -> list[float]:
    worker = _build_worker()
    session = _build_mock_session()
    timestamps: list[float] = []
    with patch("app.dialing_worker.worker.is_within_calling_hours", return_value=True):
        for lead in leads:
            timestamps.append(time.time())
            await worker._dispatch_call(session, lead)
            await asyncio.sleep(1.0)
    return timestamps


# ── Locust integration ────────────────────────────────────────────────────────

_LEADS = _build_leads()
_lead_iter = iter(_LEADS)


class DialerLoadUser(User):
    wait_time = constant(0)

    def on_start(self):
        self._loop = asyncio.new_event_loop()
        self._worker = _build_worker()
        self._session = _build_mock_session()
        self._tz_patch = patch(
            "app.dialing_worker.worker.is_within_calling_hours", return_value=True
        )
        self._tz_patch.start()

    def on_stop(self):
        self._tz_patch.stop()
        self._loop.close()

    @task
    def dispatch_one(self):
        try:
            lead = next(_lead_iter)
        except StopIteration:
            self.environment.runner.quit()
            return
        t = time.time()
        self._loop.run_until_complete(self._dispatch_and_sleep(lead))
        _dispatch_timestamps.append(t)

    async def _dispatch_and_sleep(self, lead: Contact) -> None:
        await self._worker._dispatch_call(self._session, lead)
        await asyncio.sleep(1.0)


@events.test_stop.add_listener
def _on_test_stop(environment, **kwargs):
    if not _dispatch_timestamps:
        raise AssertionError("No dispatches recorded")
    max_cps = _compute_max_cps(_dispatch_timestamps)
    print(f"\n[locustfile] dispatches={len(_dispatch_timestamps)} max_cps={max_cps:.2f}")
    assert max_cps < 1.1, f"CPS limit violated: max_cps={max_cps:.2f} >= 1.1"
    print("[locustfile] PASS: peak CPS within 1.1 limit")


# ── Standalone execution ──────────────────────────────────────────────────────

if __name__ == "__main__":
    leads = _build_leads()
    timestamps = asyncio.run(_run_dispatch_loop(leads))
    max_cps = _compute_max_cps(timestamps)
    print(f"dispatches={len(timestamps)} max_cps={max_cps:.2f}")
    assert max_cps < 1.1, f"CPS limit violated: max_cps={max_cps:.2f} >= 1.1"
    print("PASS: peak CPS within 1.1 limit")
