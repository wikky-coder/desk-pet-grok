import desk_pet_grok.secrets as secrets
from desk_pet_grok import config


def test_env_beats_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    secrets.set_api_key("file-key")
    monkeypatch.setenv("XAI_API_KEY", "env-key")
    assert secrets.get_api_key() == "env-key"


def test_file_key_when_no_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    secrets.set_api_key("file-key")
    assert secrets.get_api_key() == "file-key"


def test_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    payload = {
        "window_x": 10,
        "window_y": 20,
        "window_width": 412,
        "window_height": 344,
        "quiet": True,
        "penetrate": False,
        "bubble_visible": True,
    }
    config.save_settings(payload)
    loaded = config.load_settings()
    for key, value in payload.items():
        assert loaded[key] == value
