# Restatify Booking API

Small self-hosted API for searching free slots and creating reservations.

Version: 1.2.5

## Features

- API key protected endpoints
- Slot search based on workday hours, existing reservations and live Google availability
- Reservation creation with conflict checks
- Automatic Google Calendar event creation after successful reservation
- Cancellation tokens with API-backed reservation cancellation
- Cancellation endpoint returns subscriber context for WordPress confirmation mails
- PostgreSQL-ready via `DATABASE_URL`
- Google Calendar Free/Busy sync worker via cron (`app.sync_google_freebusy`)
- Weekly availability rules with multiple daily windows (for lunch breaks etc.)
- Optional holiday calendar type that is treated as hard blocker
- Polling-based double-booking conflict detection with deduplicated alert memory
- Optional email notification for newly detected conflicts
- Mandatory reservation-time live Google FreeBusy recheck to reduce race-condition collisions
- Optional explicit write-target calendar selection

## Compatibility

- Works with `WP Restatify Booking Assistant` as primary frontend.
- Works with `Restatify Multi Chat Overlay` indirectly via Booking Assistant handover flow.
- API itself has no runtime dependency on either WordPress plugin.

## Endpoints

- `GET /health`
- `POST /v1/slots/search`
- `POST /v1/reservations`
- `POST /v1/reservations/cancel`
- `GET /v1/config/sync`
- `PUT /v1/config/sync`

## Cron sync

- Worker command: `python -m app.sync_google_freebusy`
- Reads `GOOGLE_CREDENTIALS_JSON`
- Merges calendars from sync config (`/v1/config/sync`) with `GOOGLE_CALENDAR_IDS`
- Deduplicates IDs and syncs the combined list
- Writes synchronized busy windows into `busy_blocks`
- Calendar config supports `privacy_mode` and `calendar_type` (`general` or `holiday`)

During sync, overlaps between local reservations and fetched Google busy windows are recorded in
`booking_conflicts` and can trigger a one-time email alert per unique conflict key.

When a reservation is created, the API also creates a Google Calendar event (unless disabled).
The service account must have at least "Make changes to events" access on the target calendar.

When a reservation is cancelled via `POST /v1/reservations/cancel`, the API marks the reservation as
`cancelled`, stores cancellation reason/message, and deletes the Google Calendar event if event metadata
is available.

## Live availability checks

- Both slot search and reservation creation require working Google credentials and access to every configured calendar.
- Search fetches live availability for the bounded search window, not once per candidate slot. Reservation creation fetches it again immediately before creating the Google event.
- Every overlapping Google FreeBusy interval blocks booking, including busy all-day events. Adjacent intervals remain bookable.
- Missing calendars, malformed responses, credential errors and unavailable Google services return HTTP `503` (`BACKEND_UNAVAILABLE`), never an unchecked list of free slots or a successful reservation.
- A confirmed live overlap returns HTTP `409` (`GOOGLE_SLOT_CONFLICT`) without creating a reservation or Google event.
- General calendars respect Google's **Busy/Free** setting: events marked **Free** do not block. After converting an all-day event to a timed event, verify that it is marked **Busy**.
- Holiday calendars remain hard blockers, including transparent events; all Events API pages are read.
- Cron sync validates all calendar responses before replacing cached busy windows. Incomplete responses leave the previous cache unchanged.
- Live checks reduce stale-data collisions but cannot make Google edits and local reservations one atomic transaction.

Deploy these changes to the **Booking API and sync worker**. Updating only the WordPress plugin does not update this backend logic. No plugin API-contract or database-schema change is required.

### Regression tests

With the dependencies from `requirements.txt` installed (Python 3.11):

```powershell
python -m unittest discover -s tests -v
```

Tests use mocked Google services and an isolated in-memory database; they do not create real calendar events.

## Google reservation write env vars

- `GOOGLE_WRITE_EVENTS_ENABLED=true|false`
- `GOOGLE_WRITE_CALENDAR_ID=your-calendar-id@group.calendar.google.com`

Write target policy:

1. `write_calendar_id` from sync config (plugin) is used when set
2. otherwise `GOOGLE_WRITE_CALENDAR_ID` is used
3. if both are empty, reservation returns an error and no local reservation is persisted

## Conflict notification env vars

- `CONFLICT_NOTIFY_ENABLED=true|false`
- `CONFLICT_NOTIFY_EMAIL=alerts@example.com`
- `CONFLICT_NOTIFY_FROM=restatify-booking-api@your-domain.tld`
- `SMTP_HOST=smtp.example.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME=...`
- `SMTP_PASSWORD=...`
- `SMTP_USE_STARTTLS=true|false`
- `SMTP_USE_SSL=true|false`

## Sync config model

`calendar_sources` item fields:

- `calendar_id`
- `label`
- `privacy_mode` (`private` or `official`)
- `calendar_type` (`general` or `holiday`)

`availability_rules` format:

- weekday `0-6` (Monday = `0`)
- multiple time windows per day, e.g. `09:00-12:00` and `13:00-17:00`

Additional sync config fields (can be pushed from WordPress plugin):

- `write_events_enabled` (`true`/`false`)
- `write_calendar_id` (optional calendar ID override)

## Calendar source merge behavior

- `GOOGLE_CALENDAR_IDS` provides baseline calendars from environment configuration.
- Plugin sync config can add additional calendars via `calendar_sources`.
- The API merges both lists and removes duplicates for FreeBusy checks and sync worker runs.

## Quick start

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8088
```

## Local Docker quick start (Rancher Desktop)

1. Use Rancher Desktop with `dockerd` runtime.
2. Copy `.env.local.example` to `.env.local` and adjust values.
3. Start stack:

```bash
docker compose up -d --build
```

4. Optional sync run:

```bash
docker compose --profile manual run --rm sync
```

5. Open:

- API health: `http://localhost:8088/health`
- Mail test inbox: `http://localhost:8025`

See `RUNBOOK.md` for detailed local test commands.

## Operational smoke test script

Use the bundled script to verify health, authenticated config access and slot-search behavior from one command.

```bash
chmod +x scripts/health-sync-check.sh
API_BASE_URL="https://api.example.test" API_KEY="<your-key>" scripts/health-sync-check.sh
```

Optional: run one sync worker pass first.

```bash
API_BASE_URL="https://api.example.test" API_KEY="<your-key>" scripts/health-sync-check.sh -w
```

Notes:

- Exit code `2` means `calendar_sources` is empty in `/v1/config/sync`.
- Set `CURL_INSECURE=1` only for temporary self-signed lab setups.

For production-like Docker Compose with VPN + HTTPS, see `DOCKER_COMPOSE_VPN_HTTPS_GUIDE.md`.

## Production install

Run:

```bash
bash install.sh
```

Then edit `.env` and Caddy hostname.

## Notes

Google Calendar free/busy sync is designed to be added as a follow-up worker service.
This API already exposes the contract needed by the WordPress booking plugin and chat integration.

## Release packaging

Create the release archive from repository root. Exclude local environment files,
credentials/configuration, databases, virtual environments, caches, Git metadata,
and any prior release archives:

```bash
tar -czf release/restatify-booking-api-1.2.5.tar.gz \
  --exclude='.git' \
  --exclude='.env' --exclude='.env.*' --exclude='.env.local*' \
  --exclude='*.db*' --exclude='*.sqlite*' \
  --exclude='sync-config.json' --exclude='sync-state.json' \
  --exclude='.venv' --exclude='venv' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.pytest_cache' --exclude='.mypy_cache' \
  --exclude='gitleaks-*' --exclude='release/*.tar*' --exclude='release/*.zip' .
```

The safe `.env.example` template is intentionally excluded with other `.env.*` files;
create it separately from the repository when preparing a deployment.

The current release artifact is `release/restatify-booking-api-1.2.5.tar.gz`.
