# Local Runbook (Rancher Desktop + dockerd)

## 1) Prepare

1. Ensure Rancher Desktop uses dockerd runtime.
2. In this folder, copy `.env.local.example` to `.env.local`.
3. Set `API_KEY` and `GOOGLE_CREDENTIALS_JSON` in `.env.local`.
4. Configure calendars primarily in the WordPress Booking Assistant settings (`Calendars to sync`).
5. Keep `GOOGLE_CALENDAR_IDS` empty unless you need a standalone fallback without plugin sync config.

## 2) Start stack

- Run: `docker compose up -d --build`

Services:
- API: http://127.0.0.1:8088/health
- Mailpit UI: http://localhost:8025
- Postgres: internal to compose network (`db:5432`)

## 3) Run one sync job manually

- Run: `docker compose --profile manual run --rm sync`

## 4) Quick API checks

- Health:
  - `curl http://127.0.0.1:8088/health`
- Slot search (PowerShell example):
  - `Invoke-RestMethod -Method Post -Uri http://localhost:8088/v1/slots/search -Headers @{ 'X-API-Key'='change-me-local' } -ContentType 'application/json' -Body '{"start_iso":"2026-04-03T09:00:00+02:00","end_iso":"2026-04-10T09:00:00+02:00","duration_minutes":30,"timezone":"Europe/Berlin"}'`

## 5) One-command smoke test

From repository root:

- `chmod +x scripts/health-sync-check.sh`
- `API_BASE_URL="http://127.0.0.1:8088" API_KEY="change-me-local" scripts/health-sync-check.sh`

Optional (force one sync worker run first):

- `API_BASE_URL="http://127.0.0.1:8088" API_KEY="change-me-local" scripts/health-sync-check.sh -w`

Meaningful exit codes:

- `0`: all checks passed
- `2`: API reachable but `calendar_sources` is empty in sync config

## 6) Stop stack

- Run: `docker compose down`
- Remove volumes too (optional reset): `docker compose down -v`
