from __future__ import annotations

from datetime import datetime, timezone


def parse_google_time_value(raw_value: str) -> datetime:
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_google_event_time_data(payload: dict) -> datetime | None:
    if not isinstance(payload, dict):
        return None

    date_time_raw = str(payload.get("dateTime") or "").strip()
    if date_time_raw != "":
        try:
            return parse_google_time_value(date_time_raw)
        except ValueError:
            return None

    date_raw = str(payload.get("date") or "").strip()
    if date_raw == "":
        return None

    try:
        return parse_google_time_value(f"{date_raw}T00:00:00+00:00")
    except ValueError:
        return None


def has_time_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def is_google_all_day_range(start_utc: datetime, end_utc: datetime) -> bool:
    total_seconds = int((end_utc - start_utc).total_seconds())
    return total_seconds > 0 and total_seconds % 86400 == 0
