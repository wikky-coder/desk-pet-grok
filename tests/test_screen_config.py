from desk_pet_grok import config


def test_screen_defaults_off(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    s = config.load_settings()
    assert s["screen_aware"] is False and s["screen_vision"] is False and s["screen_proactive"] is False
    assert s["screen_limit_hour"] == 3 and s["screen_limit_day"] == 20
    config.save_settings({"screen_aware": True, "screen_usage": {"day": "x", "count": 2, "stamps": []}})
    s = config.load_settings()
    assert s["screen_aware"] is True and s["screen_usage"]["count"] == 2
