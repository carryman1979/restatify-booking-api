from __future__ import annotations

from fastapi import HTTPException


class BookingApiErrorCode:
    INVALID_API_KEY = "INVALID_API_KEY"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    START_ISO_TIMEZONE_REQUIRED = "START_ISO_TIMEZONE_REQUIRED"
    SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"
    SLOT_RESERVED = "SLOT_RESERVED"
    GOOGLE_SLOT_CONFLICT = "GOOGLE_SLOT_CONFLICT"
    CANCELLATION_TOKEN_INVALID = "CANCELLATION_TOKEN_INVALID"
    CANCELLATION_NOT_ALLOWED = "CANCELLATION_NOT_ALLOWED"


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
