# Release 1.2.5

## Highlights

- Corrected live Google Calendar availability handling for slot search and reservation creation.
- Incomplete or malformed FreeBusy data fails closed with `503 BACKEND_UNAVAILABLE`; confirmed overlaps return `409 GOOGLE_SLOT_CONFLICT`.
- Removed the general-calendar all-day exemption from live checks. Holiday calendars were already hard blockers via the separate paginated Events API path.
- The sync worker retains cached busy windows when a calendar response is incomplete.
- Added regression tests for live availability, strict FreeBusy parsing, holiday pagination, and cache preservation.

## Operations

- Deploy to the Booking API and sync worker. No WordPress plugin or database-schema update is required.
- Verify only against a test calendar after deployment; this release process does not modify real calendars.
- General-calendar all-day events must have Google **Busy** status to block; holiday calendars remain hard blockers regardless of transparency.
- This release does not establish the cause of any specific availability incident.

## Compatibility and artifact

- API version: `1.2.5`
- Backward compatible with the 1.2.x line.
- Artifact: `restatify-booking-api-1.2.5.tar.gz`
