from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import settings


def _default_calendar_sources() -> list[dict[str, str]]:
    ids = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]
    return [
        {
            "calendar_id": calendar_id,
            "label": calendar_id,
            "privacy_mode": "private",
            "calendar_type": "general",
        }
        for calendar_id in ids
    ]


def get_default_sync_config() -> dict:
    default_rules = []
    for weekday in range(5):
        default_rules.append(
            {
                "weekday": weekday,
                "windows": [
                    {"start": "09:00", "end": "12:00"},
                    {"start": "13:00", "end": "17:00"},
                ],
            }
        )

    return {
        "sync_enabled": True,
        "sync_interval_minutes": 15,
        "calendar_sources": _default_calendar_sources(),
        "availability_rules": default_rules,
    }


def _is_valid_hhmm(value: str) -> bool:
    return re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value) is not None


def _normalize_availability_rules(raw_rules) -> list[dict]:
    if not isinstance(raw_rules, list):
        return []

    normalized = []
    for rule in raw_rules:
        if not isinstance(rule, dict):
            continue

        weekday = int(rule.get("weekday", -1))
        if weekday < 0 or weekday > 6:
            continue

        windows_raw = rule.get("windows", [])
        if not isinstance(windows_raw, list):
            continue

        windows = []
        for window in windows_raw:
            if not isinstance(window, dict):
                continue

            start = str(window.get("start", "")).strip()
            end = str(window.get("end", "")).strip()
            if not _is_valid_hhmm(start) or not _is_valid_hhmm(end):
                continue
            if start >= end:
                continue

            windows.append({"start": start, "end": end})

        windows.sort(key=lambda item: item["start"])

        if len(windows) > 0:
            normalized.append(
                {
                    "weekday": weekday,
                    "windows": windows,
                }
            )

    normalized.sort(key=lambda item: int(item["weekday"]))
    return normalized


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
            "availability_rules": parsed.get("availability_rules", config["availability_rules"]),
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
        calendar_type = str(source.get("calendar_type", "general")).strip().lower()
        if calendar_type not in ("general", "holiday"):
            calendar_type = "general"
        clean_sources.append(
            {
                "calendar_id": calendar_id,
                "label": str(source.get("label", calendar_id)).strip() or calendar_id,
                "privacy_mode": privacy_mode,
                "calendar_type": calendar_type,
            }
        )

    config["calendar_sources"] = clean_sources
    config["sync_interval_minutes"] = max(5, min(720, int(config["sync_interval_minutes"])))
    config["availability_rules"] = _normalize_availability_rules(config.get("availability_rules", []))

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
            "availability_rules": config.get("availability_rules", sanitized.get("availability_rules", [])),
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
        calendar_type = str(source.get("calendar_type", "general")).strip().lower()
        if calendar_type not in ("general", "holiday"):
            calendar_type = "general"
        clean_sources.append(
            {
                "calendar_id": calendar_id,
                "label": str(source.get("label", calendar_id)).strip() or calendar_id,
                "privacy_mode": privacy_mode,
                "calendar_type": calendar_type,
            }
        )

    sanitized["calendar_sources"] = clean_sources
    sanitized["availability_rules"] = _normalize_availability_rules(sanitized.get("availability_rules", []))

    path.write_text(json.dumps(sanitized, ensure_ascii=True, indent=2), encoding="utf-8")

    return sanitized
