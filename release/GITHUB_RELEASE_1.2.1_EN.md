Title: Restatify Booking API 1.2.1

## Highlights

- Fixes live Google reservation verification so holiday calendars are checked through the Events API instead of FreeBusy
- Keeps real-time conflict protection for normal calendars while avoiding false conflicts from public holiday calendar lookups
- Improves live verification error reporting by naming whether access failed on general calendars via FreeBusy or holiday calendars via the Events API

## Compatibility

- API version: `1.2.1`
- Recommended WordPress plugin version: `1.3.1`

## Validation

- Verified inside the running Docker container that the German public holiday calendar returns `notFound` via FreeBusy but remains readable via `events.list`
- Rebuilt and restarted the API container with the patched live verification logic

## Included Artifact

- `restatify-booking-api-1.2.1.tar.gz`