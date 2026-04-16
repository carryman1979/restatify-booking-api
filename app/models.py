from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    cancel_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(190))
    email: Mapped[str] = mapped_column(String(190), index=True)
    note: Mapped[str] = mapped_column(String(1000), default="")
    timezone: Mapped[str] = mapped_column(String(64))
    start_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    end_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    cancellation_reason: Mapped[str] = mapped_column(String(120), default="")
    cancellation_message: Mapped[str] = mapped_column(String(1000), default="")
    cancelled_at_utc: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    google_event_id: Mapped[str] = mapped_column(String(190), default="")
    google_event_calendar_id: Mapped[str] = mapped_column(String(190), default="")
    created_at_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True))


class BusyBlock(Base):
    __tablename__ = "busy_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    start_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    end_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)


class BookingConflict(Base):
    __tablename__ = "booking_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conflict_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    reservation_reference: Mapped[str] = mapped_column(String(40), index=True)
    reservation_email: Mapped[str] = mapped_column(String(190), default="")
    reservation_start_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    reservation_end_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    busy_source: Mapped[str] = mapped_column(String(120), index=True)
    busy_start_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    busy_end_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    first_detected_at_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    notified_at_utc: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolved_at_utc: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
