Title: Restatify Booking API 1.2.1

## Highlights

- Behebt die Live-Google-Verifikation fuer Reservierungen, indem Feiertagskalender ueber die Events API statt ueber FreeBusy geprueft werden
- Erhaelt den Echtzeit-Konfliktschutz fuer normale Kalender, vermeidet aber Fehlkonflikte durch oeffentliche Feiertagskalender
- Praezisiert die Fehlermeldung der Live-Verifikation, indem zwischen allgemeinen Kalendern via FreeBusy und Feiertagskalendern via Events API unterschieden wird

## Kompatibilitaet

- API-Version: `1.2.1`
- Empfohlene WordPress-Plugin-Version: `1.3.1`

## Validierung

- Im laufenden Docker-Container verifiziert, dass der deutsche Feiertagskalender ueber FreeBusy `notFound` liefert, ueber `events.list` aber lesbar bleibt
- API-Container mit der korrigierten Live-Verifikationslogik neu gebaut und neu gestartet

## Enthaltenes Artefakt

- `restatify-booking-api-1.2.1.tar.gz`