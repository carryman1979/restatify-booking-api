from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BusyBlock, Reservation
from app.services.config_store import load_sync_config


def _to_utc(dt: datetime, timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)
    return dt.astimezone(timezone.utc)


def _to_zone(dt: datetime, timezone_name: str) -> datetime:
    return dt.astimezone(ZoneInfo(timezone_name))


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":", 1)
    return int(hours) * 60 + int(minutes)


def _ceil_to_quarter_hour(dt: datetime) -> datetime:
    # Remove sub-minute precision first so generated slots are clean.
    normalized = dt.replace(second=0, microsecond=0)
    minute_mod = normalized.minute % 15
    if minute_mod == 0:
        return normalized

    return normalized + timedelta(minutes=(15 - minute_mod))


def _is_in_allowed_windows(local_start: datetime, local_end: datetime, availability_rules: dict[int, list[tuple[int, int]]]) -> bool:
    windows = availability_rules.get(local_start.weekday(), [])
    if len(windows) == 0:
        return False

    start_minutes = local_start.hour * 60 + local_start.minute
    end_minutes = local_end.hour * 60 + local_end.minute

    for window_start, window_end in windows:
        if start_minutes >= window_start and end_minutes <= window_end:
            return True

    return False


def search_slots(db: Session, start_iso: datetime, end_iso: datetime, duration_minutes: int, timezone_name: str) -> list[dict[str, str]]:
    start_utc = _to_utc(start_iso, timezone_name)
    end_utc = _to_utc(end_iso, timezone_name)

    if end_utc <= start_utc:
        return []

    max_end = start_utc + timedelta(days=settings.max_window_days)
    if end_utc > max_end:
        end_utc = max_end

    stmt = select(Reservation).where(
        and_(
            Reservation.status.in_(["held", "confirmed"]),
            or_(
                and_(Reservation.start_utc >= start_utc, Reservation.start_utc < end_utc),
                and_(Reservation.end_utc > start_utc, Reservation.end_utc <= end_utc),
                and_(Reservation.start_utc <= start_utc, Reservation.end_utc >= end_utc),
            ),
        )
    )
    reservations = list(db.execute(stmt).scalars().all())

    busy_stmt = select(BusyBlock).where(
        or_(
            and_(BusyBlock.start_utc >= start_utc, BusyBlock.start_utc < end_utc),
            and_(BusyBlock.end_utc > start_utc, BusyBlock.end_utc <= end_utc),
            and_(BusyBlock.start_utc <= start_utc, BusyBlock.end_utc >= end_utc),
        )
    )
    busy_blocks = list(db.execute(busy_stmt).scalars().all())

    slots: list[dict[str, str]] = []
    cursor_local = _ceil_to_quarter_hour(_to_zone(start_utc, timezone_name))
    end_local = _to_zone(end_utc, timezone_name)

    sync_config = load_sync_config()
    availability_rules_raw = sync_config.get("availability_rules", []) if isinstance(sync_config, dict) else []
    availability_rules: dict[int, list[tuple[int, int]]] = {}
    if isinstance(availability_rules_raw, list):
        for rule in availability_rules_raw:
            if not isinstance(rule, dict):
                continue
            weekday = int(rule.get("weekday", -1))
            if weekday < 0 or weekday > 6:
                continue

            windows_raw = rule.get("windows", [])
            if not isinstance(windows_raw, list):
                continue

            windows: list[tuple[int, int]] = []
            for window in windows_raw:
                if not isinstance(window, dict):
                    continue
                start_hhmm = str(window.get("start", "")).strip()
                end_hhmm = str(window.get("end", "")).strip()
                if len(start_hhmm) != 5 or len(end_hhmm) != 5 or ":" not in start_hhmm or ":" not in end_hhmm:
                    continue
                start_minutes = _to_minutes(start_hhmm)
                end_minutes = _to_minutes(end_hhmm)
                if start_minutes >= end_minutes:
                    continue
                windows.append((start_minutes, end_minutes))

            if len(windows) > 0:
                availability_rules[weekday] = windows

    if len(availability_rules) == 0:
        for weekday in range(5):
            availability_rules[weekday] = [
                (settings.workday_start_hour * 60, settings.workday_end_hour * 60)
            ]

    minute_step = max(15, settings.slot_step_minutes)
    duration = timedelta(minutes=duration_minutes)

    while cursor_local < end_local:
        slot_end_local = cursor_local + duration
        if slot_end_local <= end_local and _is_in_allowed_windows(cursor_local, slot_end_local, availability_rules):
                slot_start_utc = cursor_local.astimezone(timezone.utc)
                slot_end_utc = slot_end_local.astimezone(timezone.utc)

                blocked = False
                for reservation in reservations:
                    if _overlaps(slot_start_utc, slot_end_utc, reservation.start_utc, reservation.end_utc):
                        blocked = True
                        break

                if not blocked:
                    for block in busy_blocks:
                        if _overlaps(slot_start_utc, slot_end_utc, block.start_utc, block.end_utc):
                            blocked = True
                            break

                if not blocked:
                    slots.append(
                        {
                            "start_iso": cursor_local.isoformat(),
                            "end_iso": slot_end_local.isoformat(),
                        }
                    )

        cursor_local = cursor_local + timedelta(minutes=minute_step)

    return slots
