Restatify Booking API 1.2.0

- Adds cancellation tokens and the POST /v1/reservations/cancel endpoint.
- Persists cancellation reason, cancellation message, cancelled timestamp, and Google event metadata.
- Deletes linked Google Calendar events on successful cancellation when metadata is available.
- Returns subscriber context in cancellation responses so the WordPress plugin can send branded confirmation mails.
- Hardens Google FreeBusy handling to fail safe when configured calendars are inaccessible.
- Ensures new reservation cancellation fields are created at runtime for existing databases.

Packaging notes

- API version: 1.2.0
- Pair with WordPress plugin release 1.3.0.
- If running in Docker without a bind mount for app code, rebuild the API image before deploying this release.