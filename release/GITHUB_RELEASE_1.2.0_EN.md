## Highlights

- Adds cancellation tokens and `POST /v1/reservations/cancel`
- Persists cancellation reason, cancellation message, cancelled timestamp, and Google event metadata
- Deletes linked Google Calendar events on successful cancellation when metadata is present
- Returns subscriber context for branded WordPress cancellation mails
- Fails safe when configured Google calendars are inaccessible during live conflict checks or sync
- Ensures required cancellation columns are created at runtime for existing databases

## Compatibility

- API version: `1.2.0`
- Recommended WordPress plugin version: `1.3.0`

## Validation

- Local reservation, cancellation, slot reopening, and mail-triggering flows verified
- Release archive rebuilt and checked to exclude Git metadata, local secret files, and nested release artifacts

## Included Artifact

- `restatify-booking-api-1.2.0.tar.gz`