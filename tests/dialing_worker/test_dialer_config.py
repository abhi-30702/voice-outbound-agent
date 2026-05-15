from app.dialing_worker.config import DialerConfig


def test_dialer_config_livekit_fields():
    cfg = DialerConfig(
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        livekit_sip_trunk_id="ST_123",
    )
    assert cfg.livekit_url == "wss://test.livekit.cloud"
    assert cfg.livekit_sip_trunk_id == "ST_123"
    assert cfg.batch_size == 50
    assert cfg.poll_interval_sec == 5
