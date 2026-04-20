from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, ensure_runtime_schema, get_db
from app.models import Reservation
from app.schemas import (
    CalendarSource,
    DayAvailability,
    ReservationCancelRequest,
    ReservationCancelResult,
    ReservationCreateRequest,
    ReservationCreateResult,
    SyncConfig,
    SlotResponse,
    SlotSearchRequest,
    SlotSearchResult,
)
from app.services.config_store import load_sync_config, save_sync_config
from app.services.slots import search_slots

app = FastAPI(title="Restatify Booking API", version="1.2.1")


@app.on_event("startup")
def startup() -> None:
    ensure_runtime_schema()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _has_time_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _get_google_calendar_ids_for_check() -> list[str]:
    sync_config = load_sync_config()
    calendar_sources = sync_config.get("calendar_sources", []) if isinstance(sync_config, dict) else []
    plugin_ids = [
        str(item.get("calendar_id", "")).strip()
        for item in calendar_sources
        if isinstance(item, dict) and str(item.get("calendar_id", "")).strip() != ""
    ]

    env_ids = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]

    merged: list[str] = []
    seen: set[str] = set()
    for calendar_id in env_ids + plugin_ids:
        if calendar_id in seen:
            continue
        seen.add(calendar_id)
        merged.append(calendar_id)

    return merged


def _get_google_calendar_ids_for_live_check() -> list[str]:
    sync_config = load_sync_config()
    calendar_sources = sync_config.get("calendar_sources", []) if isinstance(sync_config, dict) else []

    plugin_ids = [
        str(item.get("calendar_id", "")).strip()
        for item in calendar_sources
        if isinstance(item, dict)
        and str(item.get("calendar_id", "")).strip() != ""
        and str(item.get("calendar_type", "general")).strip().lower() != "holiday"
    ]

    env_ids = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]

    merged: list[str] = []
    seen: set[str] = set()
    for calendar_id in env_ids + plugin_ids:
        if calendar_id in seen:
            continue
        seen.add(calendar_id)
        merged.append(calendar_id)

    return merged


def _get_google_holiday_calendar_ids_for_live_check() -> list[str]:
    sync_config = load_sync_config()
    calendar_sources = sync_config.get("calendar_sources", []) if isinstance(sync_config, dict) else []

    merged: list[str] = []
    seen: set[str] = set()
    for item in calendar_sources:
        if not isinstance(item, dict):
            continue

        calendar_id = str(item.get("calendar_id", "")).strip()
        if calendar_id == "":
            continue

        calendar_type = str(item.get("calendar_type", "general")).strip().lower()
        if calendar_type != "holiday":
            continue

        if calendar_id in seen:
            continue

        seen.add(calendar_id)
        merged.append(calendar_id)

    return merged


def _get_google_calendar_source_map() -> dict[str, dict]:
    sync_config = load_sync_config()
    calendar_sources = sync_config.get("calendar_sources", []) if isinstance(sync_config, dict) else []

    source_map: dict[str, dict] = {}
    for item in calendar_sources:
        if not isinstance(item, dict):
            continue

        calendar_id = str(item.get("calendar_id", "")).strip()
        if calendar_id == "":
            continue

        source_map[calendar_id] = item

    return source_map


def _get_google_calendar_id_for_write() -> str:
    sync_config = load_sync_config()
    configured = str(sync_config.get("write_calendar_id", "")).strip()
    if configured == "":
        configured = settings.google_write_calendar_id.strip()
    return configured


def _is_booking_backend_configured() -> bool:
    return len(_get_google_calendar_ids_for_check()) > 0


def _ensure_booking_backend_configured() -> None:
    if _is_booking_backend_configured():
        return

    raise HTTPException(
        status_code=503,
        detail="Booking backend is currently unavailable. Please try again later.",
    )


def _parse_google_time_value(raw_value: str) -> datetime:
    return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _parse_google_event_time_data(payload: dict) -> datetime | None:
    if not isinstance(payload, dict):
        return None

    date_time_raw = str(payload.get("dateTime") or "").strip()
    if date_time_raw != "":
        try:
            return _parse_google_time_value(date_time_raw)
        except ValueError:
            return None

    date_raw = str(payload.get("date") or "").strip()
    if date_raw == "":
        return None

    try:
        return _parse_google_time_value(f"{date_raw}T00:00:00+00:00")
    except ValueError:
        return None


def _is_google_all_day_range(start_utc: datetime, end_utc: datetime) -> bool:
    total_seconds = int((end_utc - start_utc).total_seconds())
    return total_seconds > 0 and total_seconds % 86400 == 0


def _ensure_no_google_live_conflict(start_utc: datetime, end_utc: datetime) -> None:
    credentials_json = settings.google_credentials_json.strip()
    general_calendar_ids = _get_google_calendar_ids_for_live_check()
    holiday_calendar_ids = _get_google_holiday_calendar_ids_for_live_check()
    if credentials_json == "" or (len(general_calendar_ids) == 0 and len(holiday_calendar_ids) == 0):
        return

    try:
        creds_payload = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(
            creds_payload,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        # Keep reservation flow available if Google check cannot be reached.
        print(f"Google live conflict check failed: {exc}")
        return

    inaccessible_general_calendars: list[str] = []
    inaccessible_holiday_calendars: list[str] = []
    if len(general_calendar_ids) > 0:
        try:
            result = service.freebusy().query(
                body={
                    "timeMin": start_utc.isoformat(),
                    "timeMax": end_utc.isoformat(),
                    "items": [{"id": cal_id} for cal_id in general_calendar_ids],
                }
            ).execute()
        except Exception as exc:
            print(f"Google live free/busy check failed: {exc}")
            result = {}

        calendars_data = (result or {}).get("calendars", {})
        if not isinstance(calendars_data, dict):
            calendars_data = {}

        for calendar_id in general_calendar_ids:
            payload = calendars_data.get(calendar_id, {})
            if not isinstance(payload, dict):
                inaccessible_general_calendars.append(calendar_id)
                continue

            errors = payload.get("errors", [])
            if isinstance(errors, list) and len(errors) > 0:
                inaccessible_general_calendars.append(calendar_id)
                continue

            busy_ranges = payload.get("busy", []) if isinstance(payload, dict) else []
            for busy_range in busy_ranges:
                start_raw = str(busy_range.get("start") or "").strip()
                end_raw = str(busy_range.get("end") or "").strip()
                if start_raw == "" or end_raw == "":
                    continue
                try:
                    busy_start = _parse_google_time_value(start_raw)
                    busy_end = _parse_google_time_value(end_raw)
                except ValueError:
                    continue

                if not _has_time_overlap(start_utc, end_utc, busy_start, busy_end):
                    continue

                if _is_google_all_day_range(busy_start, busy_end):
                    continue

                raise HTTPException(status_code=409, detail="Slot conflicts with current Google calendar data")

    for calendar_id in holiday_calendar_ids:
        try:
            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_utc.isoformat(),
                    timeMax=end_utc.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except HttpError:
            inaccessible_holiday_calendars.append(calendar_id)
            continue
        except Exception as exc:
            print(f"Google live holiday check failed for {calendar_id}: {exc}")
            inaccessible_holiday_calendars.append(calendar_id)
            continue

        items = events_result.get("items", []) if isinstance(events_result, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue

            start_payload = item.get("start", {})
            end_payload = item.get("end", {})
            event_start = _parse_google_event_time_data(start_payload)
            event_end = _parse_google_event_time_data(end_payload)
            if event_start is None or event_end is None or event_end <= event_start:
                continue

            if _has_time_overlap(start_utc, end_utc, event_start, event_end):
                raise HTTPException(status_code=409, detail="Slot conflicts with current Google calendar data")

    if len(inaccessible_general_calendars) > 0 or len(inaccessible_holiday_calendars) > 0:
        detail_parts: list[str] = []
        if len(inaccessible_general_calendars) > 0:
            detail_parts.append(
                "general calendars via FreeBusy: " + ", ".join(inaccessible_general_calendars)
            )
        if len(inaccessible_holiday_calendars) > 0:
            detail_parts.append(
                "holiday calendars via Events API: " + ", ".join(inaccessible_holiday_calendars)
            )

        details = "; ".join(detail_parts)
        print(f"Google live conflict check failed for configured calendars: {details}")
        raise HTTPException(
            status_code=503,
            detail=(
                "Google calendar access check failed during live verification. "
                f"Please verify service account access for {details}"
            ),
        )


def _create_google_calendar_event(
    *,
    reference: str,
    name: str,
    email: str,
    note: str,
    timezone_name: str,
    start_dt: datetime,
    end_dt: datetime,
) -> tuple[str, str]:
    sync_config = load_sync_config()
    write_events_enabled = bool(sync_config.get("write_events_enabled", settings.google_write_events_enabled))
    if not write_events_enabled:
        return "", ""

    credentials_json = settings.google_credentials_json.strip()
    if credentials_json == "":
        raise HTTPException(status_code=503, detail="Google calendar write is not configured (missing credentials)")

    calendar_id = _get_google_calendar_id_for_write()
    if calendar_id == "":
        raise HTTPException(status_code=503, detail="Google calendar write is not configured (write_calendar_id is required)")

    try:
        creds_payload = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(
            creds_payload,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

        description_lines = [f"Reference: {reference}"]
        if note.strip() != "":
            description_lines.append("")
            description_lines.append(note.strip())

        body = {
            "summary": f"Booking: {name}",
            "description": "\n".join(description_lines),
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": timezone_name,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": timezone_name,
            },
            "attendees": [{"email": email}],
        }

        try:
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=body,
                sendUpdates="all",
            ).execute()
        except HttpError as exc:
            # Service accounts without domain-wide delegation cannot invite attendees.
            # Retry by creating the event without attendees and without invitation emails.
            message = str(exc)
            if "forbiddenForServiceAccounts" not in message:
                raise

            fallback_body = dict(body)
            fallback_body.pop("attendees", None)
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=fallback_body,
                sendUpdates="none",
            ).execute()
        return str(created_event.get("id", "")).strip(), calendar_id
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not create Google calendar event: {exc}") from exc


def _delete_google_calendar_event(*, calendar_id: str, event_id: str) -> None:
    credentials_json = settings.google_credentials_json.strip()
    if credentials_json == "" or calendar_id.strip() == "" or event_id.strip() == "":
        return

    try:
        creds_payload = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(
            creds_payload,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="all").execute()
    except HttpError as exc:
        status_code = getattr(getattr(exc, "resp", None), "status", None)
        if status_code == 404:
            return
        raise HTTPException(status_code=502, detail=f"Could not delete Google calendar event: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not delete Google calendar event: {exc}") from exc


def _has_local_reservation_overlap(db: Session, start_utc: datetime, end_utc: datetime) -> bool:
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
    return db.execute(stmt).scalar_one_or_none() is not None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/slots/search", response_model=SlotSearchResult, dependencies=[Depends(require_api_key)])
def slots_search(payload: SlotSearchRequest, db: Session = Depends(get_db)) -> SlotSearchResult:
    _ensure_booking_backend_configured()

    slots = search_slots(db, payload.start_iso, payload.end_iso, payload.duration_minutes, payload.timezone)
    return SlotSearchResult(
        timezone=payload.timezone,
        duration_minutes=payload.duration_minutes,
        slots=[SlotResponse(**item) for item in slots],
    )


@app.post("/v1/reservations", response_model=ReservationCreateResult, dependencies=[Depends(require_api_key)])
def create_reservation(payload: ReservationCreateRequest, db: Session = Depends(get_db)) -> ReservationCreateResult:
    _ensure_booking_backend_configured()

    start_dt = payload.start_iso
    if start_dt.tzinfo is None:
        raise HTTPException(status_code=400, detail="start_iso must include timezone")

    end_dt = start_dt + timedelta(minutes=payload.duration_minutes)

    existing = search_slots(db, payload.start_iso, end_dt, payload.duration_minutes, payload.timezone)
    start_key = payload.start_iso.isoformat()
    is_available = any(item["start_iso"] == start_key for item in existing)
    if not is_available:
        raise HTTPException(status_code=409, detail="Slot is no longer available")

    start_utc = start_dt.astimezone(timezone.utc)
    end_utc = end_dt.astimezone(timezone.utc)

    # Recheck overlap right before commit to reduce race-condition double-bookings.
    if _has_local_reservation_overlap(db, start_utc, end_utc):
        raise HTTPException(status_code=409, detail="Slot is already reserved")

    # Optional live Google check catches manual calendar changes between polling runs.
    _ensure_no_google_live_conflict(start_utc, end_utc)

    reference = "RBK-" + secrets.token_hex(5).upper()
    cancel_token = secrets.token_urlsafe(24)
    google_event_id, google_event_calendar_id = _create_google_calendar_event(
        reference=reference,
        name=payload.name,
        email=str(payload.email),
        note=payload.note,
        timezone_name=payload.timezone,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    reservation = Reservation(
        reference=reference,
        cancel_token=cancel_token,
        name=payload.name,
        email=str(payload.email),
        note=payload.note,
        timezone=payload.timezone,
        start_utc=start_utc,
        end_utc=end_utc,
        status="confirmed",
        cancellation_reason="",
        cancellation_message="",
        cancelled_at_utc=None,
        google_event_id=google_event_id,
        google_event_calendar_id=google_event_calendar_id,
        created_at_utc=datetime.now(timezone.utc),
    )

    db.add(reservation)
    db.commit()

    return ReservationCreateResult(
        reference=reference,
        cancel_token=cancel_token,
        status="confirmed",
        start_iso=payload.start_iso.isoformat(),
        end_iso=end_dt.isoformat(),
    )


@app.post("/v1/reservations/cancel", response_model=ReservationCancelResult, dependencies=[Depends(require_api_key)])
def cancel_reservation(payload: ReservationCancelRequest, db: Session = Depends(get_db)) -> ReservationCancelResult:
    stmt = select(Reservation).where(Reservation.cancel_token == payload.cancel_token)
    reservation = db.execute(stmt).scalar_one_or_none()
    if reservation is None:
        raise HTTPException(status_code=404, detail="Cancellation token is invalid")

    if reservation.status == "cancelled":
        return ReservationCancelResult(
            already_cancelled=True,
            reference=reservation.reference,
            name=reservation.name,
            email=reservation.email,
            timezone=reservation.timezone,
            cancellation_reason=reservation.cancellation_reason,
            cancellation_message=reservation.cancellation_message,
            status="cancelled",
            start_iso=reservation.start_utc.astimezone(timezone.utc).isoformat(),
            end_iso=reservation.end_utc.astimezone(timezone.utc).isoformat(),
        )

    if reservation.status not in ("confirmed", "held"):
        raise HTTPException(status_code=409, detail="Reservation can no longer be cancelled")

    _delete_google_calendar_event(
        calendar_id=reservation.google_event_calendar_id,
        event_id=reservation.google_event_id,
    )

    reservation.status = "cancelled"
    reservation.cancellation_reason = payload.reason.strip()
    reservation.cancellation_message = payload.message.strip()
    reservation.cancelled_at_utc = datetime.now(timezone.utc)
    db.add(reservation)
    db.commit()

    return ReservationCancelResult(
        already_cancelled=False,
        reference=reservation.reference,
        name=reservation.name,
        email=reservation.email,
        timezone=reservation.timezone,
        cancellation_reason=reservation.cancellation_reason,
        cancellation_message=reservation.cancellation_message,
        status="cancelled",
        start_iso=reservation.start_utc.astimezone(timezone.utc).isoformat(),
        end_iso=reservation.end_utc.astimezone(timezone.utc).isoformat(),
    )


@app.get("/v1/config/sync", response_model=SyncConfig, dependencies=[Depends(require_api_key)])
def get_sync_config() -> SyncConfig:
    config = load_sync_config()
    return SyncConfig(
        sync_enabled=bool(config.get("sync_enabled", True)),
        sync_interval_minutes=int(config.get("sync_interval_minutes", 15)),
        calendar_sources=[CalendarSource(**item) for item in config.get("calendar_sources", []) if isinstance(item, dict)],
        availability_rules=[DayAvailability(**item) for item in config.get("availability_rules", []) if isinstance(item, dict)],
        write_events_enabled=bool(config.get("write_events_enabled", settings.google_write_events_enabled)),
        write_calendar_id=str(config.get("write_calendar_id", settings.google_write_calendar_id)).strip(),
    )


@app.put("/v1/config/sync", response_model=SyncConfig, dependencies=[Depends(require_api_key)])
def update_sync_config(payload: SyncConfig) -> SyncConfig:
    config = save_sync_config(payload.model_dump())
    return SyncConfig(
        sync_enabled=bool(config.get("sync_enabled", True)),
        sync_interval_minutes=int(config.get("sync_interval_minutes", 15)),
        calendar_sources=[CalendarSource(**item) for item in config.get("calendar_sources", []) if isinstance(item, dict)],
        availability_rules=[DayAvailability(**item) for item in config.get("availability_rules", []) if isinstance(item, dict)],
        write_events_enabled=bool(config.get("write_events_enabled", settings.google_write_events_enabled)),
        write_calendar_id=str(config.get("write_calendar_id", settings.google_write_calendar_id)).strip(),
    )
