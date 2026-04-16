from __future__ import annotations

import hashlib
import json
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from sqlalchemy import and_, delete, or_, select

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, BookingConflict, BusyBlock, Reservation
from app.services.config_store import load_sync_config


SYNC_STATE_PATH = Path("./sync-state.json")


def _should_run(sync_interval_minutes: int) -> bool:
    if not SYNC_STATE_PATH.exists():
        return True

    try:
        payload = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
        last_run = datetime.fromisoformat(str(payload.get("last_sync_utc", "")).replace("Z", "+00:00"))
    except (OSError, ValueError, json.JSONDecodeError):
        return True

    now_utc = datetime.now(timezone.utc)
    return (now_utc - last_run) >= timedelta(minutes=sync_interval_minutes)


def _mark_run() -> None:
    payload = {"last_sync_utc": datetime.now(timezone.utc).isoformat()}
    SYNC_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def _parse_google_event_time(raw_value: str) -> datetime:
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _has_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _build_conflict_key(
    reservation_reference: str,
    reservation_start_utc: datetime,
    reservation_end_utc: datetime,
    busy_source: str,
    busy_start_utc: datetime,
    busy_end_utc: datetime,
) -> str:
    raw = "|".join(
        [
            reservation_reference,
            reservation_start_utc.isoformat(),
            reservation_end_utc.isoformat(),
            busy_source,
            busy_start_utc.isoformat(),
            busy_end_utc.isoformat(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:64]


def _send_conflict_notification(rows: list[BookingConflict]) -> bool:
    if len(rows) == 0:
        return True

    if not settings.conflict_notify_enabled:
        return True

    recipient = settings.conflict_notify_email.strip()
    smtp_host = settings.smtp_host.strip()
    if recipient == "" or smtp_host == "":
        print("Conflict notifications enabled but recipient or SMTP host is missing")
        return False

    message = EmailMessage()
    message["Subject"] = f"[Restatify Booking API] {len(rows)} new booking conflict(s) detected"
    message["From"] = settings.conflict_notify_from.strip() or "restatify-booking-api@localhost"
    message["To"] = recipient

    body_lines = [
        "The booking sync detected overlaps between reservations and Google busy windows.",
        "",
    ]
    for row in rows:
        body_lines.extend(
            [
                f"- Reservation: {row.reservation_reference}",
                f"  Customer: {row.reservation_email}",
                f"  Reserved: {row.reservation_start_utc.isoformat()} -> {row.reservation_end_utc.isoformat()}",
                f"  Busy Source: {row.busy_source}",
                f"  Busy Range: {row.busy_start_utc.isoformat()} -> {row.busy_end_utc.isoformat()}",
                "",
            ]
        )

    body_lines.append("This conflict key is deduplicated in booking_conflicts, so each conflict is notified once.")
    message.set_content("\n".join(body_lines))

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, settings.smtp_port, timeout=20) as smtp:
                if settings.smtp_username.strip() != "":
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, settings.smtp_port, timeout=20) as smtp:
                if settings.smtp_use_starttls:
                    smtp.starttls()
                if settings.smtp_username.strip() != "":
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except Exception as exc:
        print(f"Failed to send conflict notification email: {exc}")
        return False

    return True


def _detect_and_store_conflicts(db, now_utc: datetime, max_utc: datetime) -> None:
    reservation_stmt = select(Reservation).where(
        and_(
            Reservation.status.in_(["held", "confirmed"]),
            Reservation.end_utc > now_utc,
            Reservation.start_utc < max_utc,
        )
    )
    reservations = list(db.execute(reservation_stmt).scalars().all())

    busy_stmt = select(BusyBlock).where(
        and_(
            BusyBlock.end_utc > now_utc,
            BusyBlock.start_utc < max_utc,
        )
    )
    busy_blocks = list(db.execute(busy_stmt).scalars().all())

    detected: dict[str, dict] = {}
    for reservation in reservations:
        for block in busy_blocks:
            if not _has_overlap(reservation.start_utc, reservation.end_utc, block.start_utc, block.end_utc):
                continue

            key = _build_conflict_key(
                reservation.reference,
                reservation.start_utc,
                reservation.end_utc,
                block.source,
                block.start_utc,
                block.end_utc,
            )
            detected[key] = {
                "conflict_key": key,
                "reservation_reference": reservation.reference,
                "reservation_email": reservation.email,
                "reservation_start_utc": reservation.start_utc,
                "reservation_end_utc": reservation.end_utc,
                "busy_source": block.source,
                "busy_start_utc": block.start_utc,
                "busy_end_utc": block.end_utc,
            }

    seen_keys = set(detected.keys())

    existing_map: dict[str, BookingConflict] = {}
    if len(seen_keys) > 0:
        existing_stmt = select(BookingConflict).where(BookingConflict.conflict_key.in_(list(seen_keys)))
        for row in db.execute(existing_stmt).scalars().all():
            existing_map[row.conflict_key] = row

    rows_to_notify: list[BookingConflict] = []
    for key, payload in detected.items():
        row = existing_map.get(key)
        if row is None:
            row = BookingConflict(
                conflict_key=payload["conflict_key"],
                reservation_reference=payload["reservation_reference"],
                reservation_email=payload["reservation_email"],
                reservation_start_utc=payload["reservation_start_utc"],
                reservation_end_utc=payload["reservation_end_utc"],
                busy_source=payload["busy_source"],
                busy_start_utc=payload["busy_start_utc"],
                busy_end_utc=payload["busy_end_utc"],
                status="open",
                first_detected_at_utc=now_utc,
                last_seen_at_utc=now_utc,
                notified_at_utc=None,
                resolved_at_utc=None,
            )
            db.add(row)
            existing_map[key] = row
        else:
            row.status = "open"
            row.last_seen_at_utc = now_utc
            row.resolved_at_utc = None

        if row.notified_at_utc is None:
            rows_to_notify.append(row)

    open_stmt = select(BookingConflict).where(BookingConflict.status == "open")
    open_rows = list(db.execute(open_stmt).scalars().all())
    for row in open_rows:
        if row.conflict_key in seen_keys:
            continue
        row.status = "resolved"
        row.resolved_at_utc = now_utc

    sent = _send_conflict_notification(rows_to_notify)
    if sent:
        for row in rows_to_notify:
            row.notified_at_utc = now_utc


def run() -> None:
    if settings.google_credentials_json.strip() == "" or settings.google_calendar_ids.strip() == "":
        print("Google env fallback active")

    sync_config = load_sync_config()
    if not bool(sync_config.get("sync_enabled", True)):
        print("Google sync skipped: sync disabled in config")
        return

    sync_interval = max(5, int(sync_config.get("sync_interval_minutes", 15)))
    if not _should_run(sync_interval):
        print("Google sync skipped: interval not reached")
        return

    calendar_sources = sync_config.get("calendar_sources", []) if isinstance(sync_config.get("calendar_sources", []), list) else []
    calendar_source_map = {}
    if isinstance(calendar_sources, list):
        for source in calendar_sources:
            if not isinstance(source, dict):
                continue
            calendar_id = str(source.get("calendar_id", "")).strip()
            if calendar_id == "":
                continue
            calendar_source_map[calendar_id] = source

    plugin_calendar_ids = [
        str(item.get("calendar_id", "")).strip()
        for item in calendar_sources
        if isinstance(item, dict) and str(item.get("calendar_id", "")).strip() != ""
    ]

    env_calendar_ids = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]

    configured_calendar_ids: list[str] = []
    seen: set[str] = set()
    for calendar_id in env_calendar_ids + plugin_calendar_ids:
        if calendar_id in seen:
            continue
        seen.add(calendar_id)
        configured_calendar_ids.append(calendar_id)

    if settings.google_credentials_json.strip() == "" or len(configured_calendar_ids) == 0:
        print("Google sync skipped: missing credentials or calendar ids")
        return

    Base.metadata.create_all(bind=engine)

    creds_payload = json.loads(settings.google_credentials_json)
    credentials = Credentials.from_service_account_info(
        creds_payload,
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
    )

    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    now_utc = datetime.now(timezone.utc)
    max_utc = now_utc + timedelta(days=max(1, settings.sync_window_days))

    calendars = configured_calendar_ids
    body = {
        "timeMin": now_utc.isoformat(),
        "timeMax": max_utc.isoformat(),
        "items": [{"id": cal_id} for cal_id in calendars],
    }

    result = service.freebusy().query(body=body).execute()

    db = SessionLocal()
    try:
        db.execute(delete(BusyBlock))

        fetched_at = datetime.now(timezone.utc)
        calendars_data = (result or {}).get("calendars", {})
        for calendar_id, payload in calendars_data.items():
            busy_ranges = payload.get("busy", []) if isinstance(payload, dict) else []
            for busy_range in busy_ranges:
                start_raw = busy_range.get("start")
                end_raw = busy_range.get("end")
                if not start_raw or not end_raw:
                    continue

                start_utc = _parse_google_event_time(start_raw)
                end_utc = _parse_google_event_time(end_raw)
                if end_utc <= start_utc:
                    continue

                db.add(
                    BusyBlock(
                        source=f"google:{calendar_id}",
                        start_utc=start_utc,
                        end_utc=end_utc,
                        fetched_at_utc=fetched_at,
                    )
                )

        # Holiday calendars are treated as hard blockers by importing event ranges directly.
        for calendar_id, source in calendar_source_map.items():
            if str(source.get("calendar_type", "general")).strip().lower() != "holiday":
                continue

            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now_utc.isoformat(),
                    timeMax=max_utc.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            for item in events_result.get("items", []) if isinstance(events_result, dict) else []:
                if not isinstance(item, dict):
                    continue

                start_data = item.get("start", {})
                end_data = item.get("end", {})
                if not isinstance(start_data, dict) or not isinstance(end_data, dict):
                    continue

                start_raw = str(start_data.get("dateTime") or "").strip()
                end_raw = str(end_data.get("dateTime") or "").strip()

                if start_raw == "" or end_raw == "":
                    start_date = str(start_data.get("date") or "").strip()
                    end_date = str(end_data.get("date") or "").strip()
                    if start_date == "" or end_date == "":
                        continue
                    start_raw = f"{start_date}T00:00:00+00:00"
                    end_raw = f"{end_date}T00:00:00+00:00"

                try:
                    start_utc = _parse_google_event_time(start_raw)
                    end_utc = _parse_google_event_time(end_raw)
                except ValueError:
                    continue

                if end_utc <= start_utc:
                    continue

                db.add(
                    BusyBlock(
                        source=f"google-holiday:{calendar_id}",
                        start_utc=start_utc,
                        end_utc=end_utc,
                        fetched_at_utc=fetched_at,
                    )
                )

        db.flush()
        _detect_and_store_conflicts(db, now_utc, max_utc)

        db.commit()
        print(f"Google free/busy sync finished for {len(calendars)} calendar(s)")
        _mark_run()
    finally:
        db.close()


if __name__ == "__main__":
    run()
