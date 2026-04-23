from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml


class ConfigError(Exception):
    """Raised when required configuration is missing."""


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"YAML file must contain a dictionary: {path}")
    return data


def get_google_credentials_json() -> str:
    raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "").strip()
    if not raw:
        raise ConfigError(
            "GOOGLE_SHEETS_CREDENTIALS_JSON is required. Use a service account JSON string or base64-encoded JSON."
        )

    if raw.startswith("{"):
        json.loads(raw)
        return raw

    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        json.loads(decoded)
        return decoded
    except Exception as exc:
        raise ConfigError(
            "GOOGLE_SHEETS_CREDENTIALS_JSON is not valid JSON/base64 JSON."
        ) from exc


def get_spreadsheet_id(profile_cfg: Dict[str, Any]) -> str:
    env_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
    if env_id:
        return env_id

    sheet_cfg = profile_cfg.get("google", {})
    if isinstance(sheet_cfg, dict) and sheet_cfg.get("spreadsheet_id"):
        return str(sheet_cfg["spreadsheet_id"])

    raise ConfigError(
        "GOOGLE_SPREADSHEET_ID is required, either as env var or profile.yaml > google.spreadsheet_id"
    )


def merge_sources_config(sources_cfg: Dict[str, Any]) -> Dict[str, Any]:
    if "sources" in sources_cfg and isinstance(sources_cfg["sources"], dict):
        root = dict(sources_cfg["sources"])
    else:
        root = dict(sources_cfg)

    root.setdefault("greenhouse", [])
    root.setdefault("lever", [])
    return root
