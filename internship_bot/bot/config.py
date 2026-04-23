from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")

    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    if not isinstance(payload, dict):
        raise ConfigError(f"Config file must contain a YAML object: {path}")

    return payload


def resolve_repo_path(raw_path: str | Path, repo_root: Path) -> Path:
    maybe_path = Path(raw_path)
    if maybe_path.is_absolute():
        return maybe_path
    return (repo_root / maybe_path).resolve()


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load_service_account_info() -> dict[str, Any]:
    raw_json = optional_env("GOOGLE_SHEETS_CREDENTIALS_JSON")
    if raw_json:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ConfigError("GOOGLE_SHEETS_CREDENTIALS_JSON is not valid JSON") from exc

    credentials_path = optional_env("GOOGLE_SHEETS_CREDENTIALS_FILE")
    if credentials_path:
        path = Path(credentials_path).expanduser().resolve()
        if not path.exists():
            raise ConfigError(f"Credential file not found: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    raise ConfigError(
        "Set GOOGLE_SHEETS_CREDENTIALS_JSON or GOOGLE_SHEETS_CREDENTIALS_FILE for Sheets sync"
    )
