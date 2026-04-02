from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(190))
    email: Mapped[str] = mapped_column(String(190), index=True)
    note: Mapped[str] = mapped_column(String(1000), default="")
    timezone: Mapped[str] = mapped_column(String(64))
    start_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    end_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    created_at_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True))


class BusyBlock(Base):
    __tablename__ = "busy_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    start_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    end_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at_utc: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
