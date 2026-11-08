"""Tests for API key handling. They use a fake key and temporary files only."""

import os

import pytest

from vcp_ai.config import (
    API_KEY_VAR,
    AISettings,
    InsecureEnvFileWarning,
    MissingAPIKeyError,
    load_api_key,
    redact,
)

FAKE_KEY = "sk-test-not-a-real-key-123456"

ENABLED_CONFIG = {
    "ai": {
        "enabled": True,
        "provider": "freellmapi",
        "base_url": "https://llm.example.com/v1/",
        "model": "test-model",
    }
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Make sure no real key from the user's shell leaks into a test."""
    monkeypatch.delenv(API_KEY_VAR, raising=False)


def write_env(tmp_path, text, mode=0o600):
    env_file = tmp_path / ".env"
    env_file.write_text(text)
    os.chmod(env_file, mode)
    return env_file


def test_missing_key_raises_helpful_error(tmp_path):
    with pytest.raises(MissingAPIKeyError, match="cp .env.example .env"):
        load_api_key(tmp_path / "does-not-exist")


def test_blank_key_counts_as_missing(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}=   \n")
    with pytest.raises(MissingAPIKeyError):
        load_api_key(env_file)


def test_key_loaded_from_env_file(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    assert load_api_key(env_file) == FAKE_KEY


def test_shell_variable_wins_over_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv(API_KEY_VAR, "from-shell-key-abcdef")
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    assert load_api_key(env_file) == "from-shell-key-abcdef"


def test_warns_when_env_file_readable_by_others(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n", mode=0o644)
    with pytest.warns(InsecureEnvFileWarning, match="chmod 600"):
        load_api_key(env_file)


def test_key_never_appears_in_repr(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    settings = AISettings.from_config(ENABLED_CONFIG, env_file=env_file)
    assert settings.api_key == FAKE_KEY
    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings)


def test_redact_hides_the_key():
    shown = redact(FAKE_KEY)
    assert FAKE_KEY not in shown
    assert "123456" not in shown


def test_disabled_ai_needs_no_key():
    settings = AISettings.from_config({"ai": {"enabled": False}}, env_file=None)
    assert settings.enabled is False
    assert settings.api_key == ""


def test_missing_ai_block_means_disabled():
    assert AISettings.from_config({}, env_file=None).enabled is False


def test_trailing_slash_removed_from_base_url(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    settings = AISettings.from_config(ENABLED_CONFIG, env_file=env_file)
    assert settings.base_url == "https://llm.example.com/v1"


def test_rejects_plain_http_for_remote_hosts(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    config = {"ai": {**ENABLED_CONFIG["ai"], "base_url": "http://llm.example.com/v1"}}
    with pytest.raises(ValueError, match="https"):
        AISettings.from_config(config, env_file=env_file)


def test_allows_http_for_localhost(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    config = {"ai": {**ENABLED_CONFIG["ai"], "base_url": "http://localhost:8080/v1"}}
    assert AISettings.from_config(config, env_file=env_file).base_url == "http://localhost:8080/v1"


def test_requires_model_and_base_url(tmp_path):
    env_file = write_env(tmp_path, f"{API_KEY_VAR}={FAKE_KEY}\n")
    config = {"ai": {"enabled": True, "base_url": "", "model": ""}}
    with pytest.raises(ValueError, match="ai.model is empty"):
        AISettings.from_config(config, env_file=env_file)
