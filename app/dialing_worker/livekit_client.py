import json
import logging
from typing import Any

from livekit.api import LiveKitAPI, CreateRoomRequest, CreateSIPParticipantRequest

from app.dialing_worker.errors import DialerError

logger = logging.getLogger(__name__)


class LiveKitClient:
    """Thin async wrapper around the LiveKit room and SIP APIs.

    Creates one room per outbound call, then dials the lead via SIP.
    All errors are wrapped in DialerError(retriable=True).
    """

    def __init__(self, url: str, api_key: str, api_secret: str, sip_trunk_id: str) -> None:
        self._api = LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)
        self._sip_trunk_id = sip_trunk_id

    async def create_room(self, room_name: str, metadata: dict[str, Any]) -> None:
        """Create a LiveKit room with lead metadata embedded as JSON."""
        try:
            await self._api.room.create_room(
                CreateRoomRequest(name=room_name, metadata=json.dumps(metadata))
            )
            logger.info("LiveKit room created", extra={"room_name": room_name})
        except Exception as exc:
            raise DialerError(
                message=f"LiveKit create_room failed: {exc}",
                retriable=True,
            ) from exc

    async def create_sip_participant(self, room_name: str, to_number: str) -> None:
        """Dial out to a PSTN number via the configured SIP trunk."""
        try:
            await self._api.sip.create_sip_participant(
                CreateSIPParticipantRequest(
                    sip_trunk_id=self._sip_trunk_id,
                    sip_call_to=to_number,
                    room_name=room_name,
                    participant_identity=f"sip-{to_number}",
                )
            )
            logger.info(
                "SIP participant created",
                extra={"room_name": room_name, "to_number": to_number},
            )
        except Exception as exc:
            raise DialerError(
                message=f"LiveKit create_sip_participant failed: {exc}",
                retriable=True,
            ) from exc

    async def close(self) -> None:
        """Close the underlying API client."""
        await self._api.aclose()
