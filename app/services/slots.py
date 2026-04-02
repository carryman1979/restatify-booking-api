from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BusyBlock, Reservation


def _to_utc(dt: datetime, timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)
    return dt.astimezone(timezone.utc)


def _to_zone(dt: datetime, timezone_name: str) -> datetime:
    return dt.astimezone(ZoneInfo(timezone_name))


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


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
    cursor_local = _to_zone(start_utc, timezone_name)
    end_local = _to_zone(end_utc, timezone_name)

    minute_step = max(15, settings.slot_step_minutes)
    duration = timedelta(minutes=duration_minutes)

    while cursor_local < end_local:
        if settings.workday_start_hour <= cursor_local.hour < settings.workday_end_hour:
            slot_end_local = cursor_local + duration
            if slot_end_local <= end_local and slot_end_local.hour <= settings.workday_end_hour:
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
