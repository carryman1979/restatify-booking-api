from __future__ import annotations

from datetime import datetime, timezone


def parse_google_time_value(raw_value: str) -> datetime:
    parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Google time must include a timezone")
    return parsed.astimezone(timezone.utc)


def parse_google_busy_response(result: object, calendar_ids: list[str]) -> dict[str, list[tuple[datetime, datetime]]]:
    """Reject incomplete calendars before any cached busy data can be replaced."""
    calendars = result.get("calendars") if isinstance(result, dict) else None
    if not isinstance(calendars, dict):
        raise ValueError("Google response is missing calendar data")
    parsed: dict[str, list[tuple[datetime, datetime]]] = {}
    for calendar_id in calendar_ids:
        payload = calendars.get(calendar_id)
        if not isinstance(payload, dict):
            raise ValueError("Google response is missing a configured calendar")
        errors = payload.get("errors", [])
        busy = payload.get("busy")
        if not isinstance(errors, list) or errors or not isinstance(busy, list):
            raise ValueError("Google calendar availability could not be verified")
        ranges: list[tuple[datetime, datetime]] = []
        for item in busy:
            if not isinstance(item, dict):
                raise ValueError("Invalid Google busy range")
            start_raw, end_raw = item.get("start"), item.get("end")
            if not isinstance(start_raw, str) or not isinstance(end_raw, str):
                raise ValueError("Invalid Google busy timestamps")
            start, end = parse_google_time_value(start_raw), parse_google_time_value(end_raw)
            if end <= start:
                raise ValueError("Invalid Google busy interval")
            ranges.append((start, end))
        parsed[calendar_id] = ranges
    return parsed


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
