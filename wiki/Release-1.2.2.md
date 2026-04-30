# Release 1.2.2

Version 1.2.2 ergänzt einen operativen Smoke-Test-Workflow fuer API-Betrieb und Troubleshooting.

## Highlights

- Neues Script `scripts/health-sync-check.sh`
- Ein-Kommando-Pruefung fuer:
  - API Health (`/health`)
  - Authentifizierter Config-Zugriff (`/v1/config/sync`)
  - Slot-Suche (`/v1/slots/search`)
- Optionaler Vorlauf mit manuellem Sync-Worker (`-w`)
- Klare Exit-Codes fuer Betrieb und CI

## Dokumentation

- README um `Operational smoke test script` erweitert
- RUNBOOK um Abschnitt `One-command smoke test` erweitert

## Kompatibilitaet

- API-Version: 1.2.2
- Empfohlene WordPress-Plugin-Version: 1.3.3

## Enthaltenes Artefakt

- `restatify-booking-api-1.2.2.tar.gz`
