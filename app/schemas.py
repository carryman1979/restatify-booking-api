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
