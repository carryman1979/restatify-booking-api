# Restatify Booking API

Small self-hosted API for searching free slots and creating reservations.

## Features

- API key protected endpoints
- Slot search based on workday hours and existing reservations
- Reservation creation with conflict checks
- PostgreSQL-ready via `DATABASE_URL`
- Google Calendar Free/Busy sync worker via cron (`app.sync_google_freebusy`)
- Weekly availability rules with multiple daily windows (for lunch breaks etc.)
- Optional holiday calendar type that is treated as hard blocker

## Endpoints

- `GET /health`
- `POST /v1/slots/search`
- `POST /v1/reservations`
- `GET /v1/config/sync`
- `PUT /v1/config/sync`

## Cron sync

- Worker command: `python -m app.sync_google_freebusy`
- Reads `GOOGLE_CREDENTIALS_JSON` and `GOOGLE_CALENDAR_IDS`
- Writes synchronized busy windows into `busy_blocks`
- Calendar config supports `privacy_mode` and `calendar_type` (`general` or `holiday`)

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

## Production install

Run:

```bash
bash install.sh
```

Then edit `.env` and Caddy hostname.

## Notes

Google Calendar free/busy sync is designed to be added as a follow-up worker service.
This API already exposes the contract needed by the WordPress booking plugin and chat integration.
