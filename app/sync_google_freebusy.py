from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, BusyBlock
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
    configured_calendar_ids = [
        str(item.get("calendar_id", "")).strip()
        for item in calendar_sources
        if isinstance(item, dict) and str(item.get("calendar_id", "")).strip() != ""
    ]

    if len(configured_calendar_ids) == 0:
        configured_calendar_ids = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]

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

                start_utc = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
                end_utc = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
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

        db.commit()
        print(f"Google free/busy sync finished for {len(calendars)} calendar(s)")
        _mark_run()
    finally:
        db.close()


if __name__ == "__main__":
    run()
