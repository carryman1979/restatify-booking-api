from datetime import datetime

from googleapiclient.discovery import Resource

from app.shared.time_utils import parse_google_event_time_data


def fetch_holiday_busy_ranges(
    service: Resource, calendar_id: str, start_utc: datetime, end_utc: datetime,
) -> list[tuple[datetime, datetime]]:
    """Read every Events page, including transparent holidays as hard blockers."""
    ranges: list[tuple[datetime, datetime]] = []
    page_token = None
    seen_tokens: set[str] = set()
    while True:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_utc.isoformat(),
            timeMax=end_utc.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
        ).execute()
        items = result.get("items") if isinstance(result, dict) else None
        if not isinstance(items, list):
            raise ValueError("Invalid Google holiday response")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Invalid Google holiday event")
            if item.get("status") == "cancelled":
                continue
            start = parse_google_event_time_data(item.get("start"))
            end = parse_google_event_time_data(item.get("end"))
            if start is None or end is None or end <= start:
                raise ValueError("Invalid Google holiday interval")
            ranges.append((start, end))
        page_token = result.get("nextPageToken")
        if not page_token:
            return ranges
        if not isinstance(page_token, str) or page_token in seen_tokens:
            raise ValueError("Invalid Google holiday pagination")
        seen_tokens.add(page_token)
