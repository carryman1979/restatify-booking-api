Title: Restatify Booking API 1.2.0

## Highlights

- Führt Cancel-Tokens und `POST /v1/reservations/cancel` ein
- Persistiert Stornogrund, Stornonachricht, Storno-Zeitpunkt und Google-Event-Metadaten
- Löscht verknüpfte Google-Kalenderevents bei erfolgreicher Stornierung, sofern Metadaten vorhanden sind
- Liefert Teilnehmerkontext für gebrandete WordPress-Stornomails zurück
- Verhält sich fail-safe, wenn konfigurierte Google-Kalender bei Live-Konfliktprüfung oder Sync nicht erreichbar sind
- Stellt sicher, dass benötigte Storno-Spalten bei bestehenden Datenbanken zur Laufzeit angelegt werden

## Kompatibilität

- API-Version: `1.2.0`
- Empfohlene WordPress-Plugin-Version: `1.3.0`

## Validierung

- Lokale Reservierungs-, Storno-, Slot-Reopen- und Mail-Trigger-Flows verifiziert
- Release-Archiv neu gebaut und darauf geprüft, dass Git-Metadaten, lokale Secret-Dateien und verschachtelte Release-Artefakte ausgeschlossen sind

## Enthaltenes Artefakt

- `restatify-booking-api-1.2.0.tar.gz`