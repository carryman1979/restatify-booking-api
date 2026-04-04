from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SlotSearchRequest(BaseModel):
    start_iso: datetime
    end_iso: datetime
    duration_minutes: int = Field(default=30, ge=15, le=180)
    timezone: str = "Europe/Berlin"


class SlotResponse(BaseModel):
    start_iso: str
    end_iso: str


class SlotSearchResult(BaseModel):
    timezone: str
    duration_minutes: int
    slots: list[SlotResponse]


class ReservationCreateRequest(BaseModel):
    start_iso: datetime
    duration_minutes: int = Field(default=30, ge=15, le=180)
    timezone: str = "Europe/Berlin"
    name: str = Field(min_length=2, max_length=190)
    email: EmailStr
    note: str = Field(default="", max_length=1000)


class ReservationCreateResult(BaseModel):
    reference: str
    status: str
    start_iso: str
    end_iso: str


class CalendarSource(BaseModel):
    calendar_id: str = Field(min_length=3, max_length=190)
    label: str = Field(default="", max_length=190)
    privacy_mode: str = Field(default="private")
    calendar_type: str = Field(default="general")


class TimeWindow(BaseModel):
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class DayAvailability(BaseModel):
    weekday: int = Field(ge=0, le=6)
    windows: list[TimeWindow] = Field(default_factory=list)


class SyncConfig(BaseModel):
    sync_enabled: bool = True
    sync_interval_minutes: int = Field(default=15, ge=5, le=720)
    calendar_sources: list[CalendarSource] = Field(default_factory=list)
    availability_rules: list[DayAvailability] = Field(default_factory=list)
    write_events_enabled: bool = True
    write_calendar_id: str = Field(default="", max_length=190)
