Titel: Restatify Booking API 1.2.5

## Highlights

- Korrigierte Live-Verfügbarkeitsprüfung für Google Kalender bei Suche und Reservierung.
- Unvollständige oder fehlerhafte FreeBusy-Daten führen geschlossen zu `503 BACKEND_UNAVAILABLE`; bestätigte Überschneidungen zu `409 GOOGLE_SLOT_CONFLICT`.
- Die bisherige Ausnahme für ganztägige Termine in allgemeinen Kalendern wurde entfernt. Feiertagskalender waren bereits über den separaten, paginierten Events-API-Pfad harte Blocker.
- Der Sync-Worker erhält den bisherigen Cache, wenn eine Kalenderantwort unvollständig ist.
- Regressionstests für Live-Verfügbarkeit, Parsing, Feiertags-Paginierung und Cache-Erhalt ergänzt.

## Betriebshinweise

- Dieses Release für Booking-API und Sync-Worker bereitstellen; ein WordPress-Plugin- oder Datenbankschema-Update ist nicht erforderlich.
- Nach der Bereitstellung ausschließlich mit einem Testkalender prüfen. Im Rahmen dieses Releases wurden keine echten Kalender verändert.
- Ganztägige Termine in allgemeinen Kalendern müssen zum Blockieren als **Beschäftigt** markiert sein; Feiertagskalender bleiben unabhängig von der Transparenz harte Blocker.
- Die Ursache eines konkreten Verfügbarkeitsvorfalls wird durch dieses Release nicht belegt.

## Kompatibilität

- API-Version: `1.2.5`
- Rückwärtskompatibel zur 1.2.x-Linie.

## Enthaltenes Artefakt

- `restatify-booking-api-1.2.5.tar.gz`
