# Restatify Booking API

Small self-hosted API for searching free slots and creating reservations.

Version: 1.1.1

## Features

- API key protected endpoints
- Slot search based on workday hours and existing reservations
- Reservation creation with conflict checks
- PostgreSQL-ready via `DATABASE_URL`
- Google Calendar Free/Busy sync worker via cron (`app.sync_google_freebusy`)
- Weekly availability rules with multiple daily windows (for lunch breaks etc.)
- Optional holiday calendar type that is treated as hard blocker
- Polling-based double-booking conflict detection with deduplicated alert memory
- Optional email notification for newly detected conflicts
- Reservation-time live Google FreeBusy recheck to reduce race-condition collisions

## Compatibility

- Works with `WP Restatify Booking Assistant` as primary frontend.
- Works with `Restatify Multi Chat Overlay` indirectly via Booking Assistant handover flow.
- API itself has no runtime dependency on either WordPress plugin.

## Endpoints

- `GET /health`
- `POST /v1/slots/search`
- `POST /v1/reservations`
- `GET /v1/config/sync`
- `PUT /v1/config/sync`

## Cron sync

- Worker command: `python -m app.sync_google_freebusy`
- Reads `GOOGLE_CREDENTIALS_JSON`
- Uses calendars from sync config (`/v1/config/sync`) as primary source
- Uses `GOOGLE_CALENDAR_IDS` only as fallback when no sync config calendars are present
- Writes synchronized busy windows into `busy_blocks`
- Calendar config supports `privacy_mode` and `calendar_type` (`general` or `holiday`)

During sync, overlaps between local reservations and fetched Google busy windows are recorded in
`booking_conflicts` and can trigger a one-time email alert per unique conflict key.

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

Create a release archive from repository root:

```bash
tar -czf release/restatify-booking-api-1.1.1.tar.gz --exclude='.git' .
```
