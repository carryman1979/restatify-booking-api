from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_db
from app.models import Reservation
from app.schemas import (
    CalendarSource,
    DayAvailability,
    ReservationCreateRequest,
    ReservationCreateResult,
    SyncConfig,
    SlotResponse,
    SlotSearchRequest,
    SlotSearchResult,
)
from app.services.config_store import load_sync_config, save_sync_config
from app.services.slots import search_slots

app = FastAPI(title="Restatify Booking API", version="1.1.0")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/slots/search", response_model=SlotSearchResult, dependencies=[Depends(require_api_key)])
def slots_search(payload: SlotSearchRequest, db: Session = Depends(get_db)) -> SlotSearchResult:
    slots = search_slots(db, payload.start_iso, payload.end_iso, payload.duration_minutes, payload.timezone)
    return SlotSearchResult(
        timezone=payload.timezone,
        duration_minutes=payload.duration_minutes,
        slots=[SlotResponse(**item) for item in slots],
    )


@app.post("/v1/reservations", response_model=ReservationCreateResult, dependencies=[Depends(require_api_key)])
def create_reservation(payload: ReservationCreateRequest, db: Session = Depends(get_db)) -> ReservationCreateResult:
    start_dt = payload.start_iso
    if start_dt.tzinfo is None:
        raise HTTPException(status_code=400, detail="start_iso must include timezone")

    end_dt = start_dt + timedelta(minutes=payload.duration_minutes)

    existing = search_slots(db, payload.start_iso, end_dt, payload.duration_minutes, payload.timezone)
    start_key = payload.start_iso.isoformat()
    is_available = any(item["start_iso"] == start_key for item in existing)
    if not is_available:
        raise HTTPException(status_code=409, detail="Slot is no longer available")

    reference = "RBK-" + secrets.token_hex(5).upper()
    reservation = Reservation(
        reference=reference,
        name=payload.name,
        email=str(payload.email),
        note=payload.note,
        timezone=payload.timezone,
        start_utc=start_dt.astimezone(timezone.utc),
        end_utc=end_dt.astimezone(timezone.utc),
        status="confirmed",
        created_at_utc=datetime.now(timezone.utc),
    )
    db.add(reservation)
    db.commit()

    return ReservationCreateResult(
        reference=reference,
        status="confirmed",
        start_iso=payload.start_iso.isoformat(),
        end_iso=end_dt.isoformat(),
    )


@app.get("/v1/config/sync", response_model=SyncConfig, dependencies=[Depends(require_api_key)])
def get_sync_config() -> SyncConfig:
    config = load_sync_config()
    return SyncConfig(
        sync_enabled=bool(config.get("sync_enabled", True)),
        sync_interval_minutes=int(config.get("sync_interval_minutes", 15)),
        calendar_sources=[CalendarSource(**item) for item in config.get("calendar_sources", []) if isinstance(item, dict)],
        availability_rules=[DayAvailability(**item) for item in config.get("availability_rules", []) if isinstance(item, dict)],
    )


@app.put("/v1/config/sync", response_model=SyncConfig, dependencies=[Depends(require_api_key)])
def update_sync_config(payload: SyncConfig) -> SyncConfig:
    config = save_sync_config(payload.model_dump())
    return SyncConfig(
        sync_enabled=bool(config.get("sync_enabled", True)),
        sync_interval_minutes=int(config.get("sync_interval_minutes", 15)),
        calendar_sources=[CalendarSource(**item) for item in config.get("calendar_sources", []) if isinstance(item, dict)],
        availability_rules=[DayAvailability(**item) for item in config.get("availability_rules", []) if isinstance(item, dict)],
    )
