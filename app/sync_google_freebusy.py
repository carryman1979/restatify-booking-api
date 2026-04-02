from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, BusyBlock


def run() -> None:
    if settings.google_credentials_json.strip() == "" or settings.google_calendar_ids.strip() == "":
        print("Google sync skipped: GOOGLE_CREDENTIALS_JSON or GOOGLE_CALENDAR_IDS missing")
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

    calendars = [item.strip() for item in settings.google_calendar_ids.split(",") if item.strip() != ""]
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
    finally:
        db.close()


if __name__ == "__main__":
    run()
