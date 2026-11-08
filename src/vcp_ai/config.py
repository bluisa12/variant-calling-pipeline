"""Settings for the AI steps, and safe loading of the API key.

Security rules this module enforces:
  - The key comes only from the FREELLMAPI_API_KEY environment variable, which
    may be filled from a local .env file. It is never read from config.yaml.
  - A variable already set in the shell wins over .env (override=False).
  - The key is never included in repr(), error messages or logs.
  - A missing key fails loudly with instructions, never silently.
  - A .env file readable by other users triggers a warning.
"""

from __future__ import annotations

import os
import stat
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

API_KEY_VAR = "FREELLMAPI_API_KEY"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


class MissingAPIKeyError(RuntimeError):
    """Raised when the API key is not set."""


class InsecureEnvFileWarning(UserWarning):
    """Raised when .env can be read by users other than the owner."""


def _check_env_file_permissions(env_file: Path) -> None:
    mode = env_file.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        warnings.warn(
            f"{env_file} can be read by other users on this computer. "
            f"Restrict it with:  chmod 600 {env_file}",
            InsecureEnvFileWarning,
            stacklevel=3,
        )


def load_api_key(env_file: Path | str | None = DEFAULT_ENV_FILE) -> str:
    """Return the API key from the environment (or .env), or raise a helpful error."""
    if env_file is not None:
        env_file = Path(env_file)
        if env_file.is_file():
            _check_env_file_permissions(env_file)
            load_dotenv(env_file, override=False)

    key = os.environ.get(API_KEY_VAR, "").strip()
    if not key:
        raise MissingAPIKeyError(
            f"{API_KEY_VAR} is not set. The AI steps need it; the core pipeline does not.\n"
            f"  1. cp .env.example .env && chmod 600 .env\n"
            f"  2. Open .env in a text editor and paste your key after {API_KEY_VAR}=\n"
            f"Never commit .env or paste the key into code, config or chat."
        )
    return key


def redact(secret: str) -> str:
    """Safe-to-print stand-in for a secret, e.g. for confirming which key is loaded."""
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}…{secret[-2:]} ({len(secret)} chars)"


@dataclass(frozen=True)
class AISettings:
    """The `ai:` block of config.yaml plus the API key (hidden from repr)."""

    enabled: bool
    provider: str
    base_url: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_seconds: int = 60
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_config(cls, config: dict, env_file: Path | str | None = DEFAULT_ENV_FILE) -> "AISettings":
        """Build settings from the pipeline config. Loads the key only if AI is enabled."""
        ai = dict(config.get("ai") or {})
        enabled = bool(ai.get("enabled", False))
        settings = cls(
            enabled=enabled,
            provider=str(ai.get("provider", "")),
            base_url=str(ai.get("base_url", "")).rstrip("/"),
            model=str(ai.get("model", "")),
            temperature=float(ai.get("temperature", 0.0)),
            max_tokens=int(ai.get("max_tokens", 1024)),
            timeout_seconds=int(ai.get("timeout_seconds", 60)),
            api_key=load_api_key(env_file) if enabled else "",
        )
        if enabled:
            settings.validate()
        return settings

    def validate(self) -> None:
        problems = []
        if not self.model:
            problems.append("ai.model is empty")
        if not self.base_url:
            problems.append("ai.base_url is empty")
        else:
            url = urlparse(self.base_url)
            local = url.hostname in ("localhost", "127.0.0.1", "::1")
            if url.scheme != "https" and not local:
                problems.append("ai.base_url must use https:// so the key is encrypted in transit")
        if problems:
            raise ValueError("Invalid AI settings in config/config.yaml: " + "; ".join(problems))
