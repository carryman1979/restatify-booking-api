# Local Runbook (Rancher Desktop + dockerd)

## 1) Prepare

1. Ensure Rancher Desktop uses dockerd runtime.
2. In this folder, copy `.env.local.example` to `.env.local`.
3. Set `API_KEY` and, if needed, Google values in `.env.local`.

## 2) Start stack

- Run: `docker compose up -d --build`

Services:
- API: http://localhost:8088/health
- Mailpit UI: http://localhost:8025
- Postgres: internal to compose network (`db:5432`)

## 3) Run one sync job manually

- Run: `docker compose --profile manual run --rm sync`

## 4) Quick API checks

- Health:
  - `curl http://localhost:8088/health`
- Slot search (PowerShell example):
  - `Invoke-RestMethod -Method Post -Uri http://localhost:8088/v1/slots/search -Headers @{ 'X-API-Key'='change-me-local' } -ContentType 'application/json' -Body '{"start_iso":"2026-04-03T09:00:00+02:00","end_iso":"2026-04-10T09:00:00+02:00","duration_minutes":30,"timezone":"Europe/Berlin"}'`

## 5) Stop stack

- Run: `docker compose down`
- Remove volumes too (optional reset): `docker compose down -v`
