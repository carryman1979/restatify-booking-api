# Restatify Booking API

Small self-hosted API for searching free slots and creating reservations.

## Features

- API key protected endpoints
- Slot search based on workday hours and existing reservations
- Reservation creation with conflict checks
- PostgreSQL-ready via `DATABASE_URL`
- Google Calendar Free/Busy sync worker via cron (`app.sync_google_freebusy`)

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
- Uses persisted sync config (`sync-config.json`) for interval, enabled flag, and calendar list

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
