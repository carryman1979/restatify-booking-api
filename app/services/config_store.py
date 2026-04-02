from __future__ import annotations

import json
from pathlib import Path

from app.config import settings


def _default_calendar_sources() -> list[dict[str, str]]:
    ids = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]
    return [
        {
            "calendar_id": calendar_id,
            "label": calendar_id,
            "privacy_mode": "private",
        }
        for calendar_id in ids
    ]


def get_default_sync_config() -> dict:
    return {
        "sync_enabled": True,
        "sync_interval_minutes": 15,
        "calendar_sources": _default_calendar_sources(),
    }


def load_sync_config() -> dict:
    path = Path(settings.sync_config_path)
    if not path.exists():
        return get_default_sync_config()

    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return get_default_sync_config()

    if not isinstance(parsed, dict):
        return get_default_sync_config()

    config = get_default_sync_config()
    config.update(
        {
            "sync_enabled": bool(parsed.get("sync_enabled", config["sync_enabled"])),
            "sync_interval_minutes": int(parsed.get("sync_interval_minutes", config["sync_interval_minutes"])),
            "calendar_sources": parsed.get("calendar_sources", config["calendar_sources"]),
        }
    )

    clean_sources = []
    for source in config["calendar_sources"] if isinstance(config["calendar_sources"], list) else []:
        if not isinstance(source, dict):
            continue
        calendar_id = str(source.get("calendar_id", "")).strip()
        if calendar_id == "":
            continue
        privacy_mode = str(source.get("privacy_mode", "private")).strip().lower()
        if privacy_mode not in ("private", "official"):
            privacy_mode = "private"
        clean_sources.append(
            {
                "calendar_id": calendar_id,
                "label": str(source.get("label", calendar_id)).strip() or calendar_id,
                "privacy_mode": privacy_mode,
            }
        )

    config["calendar_sources"] = clean_sources
    config["sync_interval_minutes"] = max(5, min(720, int(config["sync_interval_minutes"])))

    return config


def save_sync_config(config: dict) -> dict:
    path = Path(settings.sync_config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sanitized = load_sync_config()
    sanitized.update(
        {
            "sync_enabled": bool(config.get("sync_enabled", sanitized["sync_enabled"])),
            "sync_interval_minutes": max(5, min(720, int(config.get("sync_interval_minutes", sanitized["sync_interval_minutes"])) )) ,
            "calendar_sources": config.get("calendar_sources", sanitized["calendar_sources"]),
        }
    )

    clean_sources = []
    for source in sanitized["calendar_sources"] if isinstance(sanitized["calendar_sources"], list) else []:
        if not isinstance(source, dict):
            continue
        calendar_id = str(source.get("calendar_id", "")).strip()
        if calendar_id == "":
            continue
        privacy_mode = str(source.get("privacy_mode", "private")).strip().lower()
        if privacy_mode not in ("private", "official"):
            privacy_mode = "private"
        clean_sources.append(
            {
                "calendar_id": calendar_id,
                "label": str(source.get("label", calendar_id)).strip() or calendar_id,
                "privacy_mode": privacy_mode,
            }
        )

    sanitized["calendar_sources"] = clean_sources

    path.write_text(json.dumps(sanitized, ensure_ascii=True, indent=2), encoding="utf-8")

    return sanitized
