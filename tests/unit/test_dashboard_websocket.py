import pytest
from unittest.mock import AsyncMock
from app.dashboard_api.websocket import ConnectionManager


@pytest.mark.asyncio
async def test_connect_adds_to_set():
    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect(ws)
    assert ws in manager._connections


@pytest.mark.asyncio
async def test_disconnect_removes_from_set():
    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager._connections


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connected():
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.broadcast({"event": "test"})
    ws1.send_json.assert_called_once_with({"event": "test"})
    ws2.send_json.assert_called_once_with({"event": "test"})


@pytest.mark.asyncio
async def test_broadcast_skips_and_removes_disconnected_client():
    manager = ConnectionManager()
    ws = AsyncMock()
    ws.send_json.side_effect = Exception("disconnected")
    await manager.connect(ws)
    await manager.broadcast({"event": "test"})  # must not raise
    assert ws not in manager._connections


@pytest.mark.asyncio
async def test_broadcast_with_no_connections_is_noop():
    manager = ConnectionManager()
    await manager.broadcast({"event": "test"})  # must not raise


@pytest.mark.asyncio
async def test_disconnect_nonexistent_is_noop():
    manager = ConnectionManager()
    ws = AsyncMock()
    manager.disconnect(ws)  # must not raise
