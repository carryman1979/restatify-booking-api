Title: Restatify Booking API 1.2.5

## Highlights

- Corrected live Google Calendar availability handling for slot search and reservation creation.
- Incomplete or malformed FreeBusy data fails closed with `503 BACKEND_UNAVAILABLE`; confirmed overlaps return `409 GOOGLE_SLOT_CONFLICT`.
- The prior general-calendar all-day exemption is removed. Holiday calendars were already hard blockers via the separate paginated Events API path.
- The sync worker retains cached busy windows when a calendar response is incomplete.
- Added regression coverage for live availability, parsing, holiday paging, and cache preservation.

## Operational notes

- Deploy this release to the Booking API and sync worker; no WordPress plugin or database-schema update is required.
- Verify with a test calendar only after deployment. No real-calendar mutations were performed as part of this release.
- General-calendar all-day events must be marked **Busy** to block availability; holiday calendars remain hard blockers regardless of transparency.
- This release does not establish the cause of any particular availability incident.

## Compatibility

- API version: `1.2.5`
- Backward compatible with the 1.2.x line.

## Included artifact

- `restatify-booking-api-1.2.5.tar.gz`
