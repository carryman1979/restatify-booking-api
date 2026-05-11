# Restatify Booking API

Die Restatify Booking API ist das Backend für Terminlogik, Slot-Suche, Reservierungen, Stornierungen und Kalendersynchronisation innerhalb des Restatify-Ökosystems.

Sie dient als zentrales System für WordPress-Integrationen wie den Booking Assistant und optionale Chat-/Handover-Flows.

## Rolle im System

Die API übernimmt die zentrale Terminlogik und wird von den WordPress-Komponenten genutzt für:

- Suche nach freien Slots
- Reservierung von Terminen
- Verwaltung von Referenzen und Cancel-Tokens
- Stornierung bestehender Reservierungen
- Kalender-Synchronisierung
- Fehler- und Validierungsrückgaben für Frontend und WordPress-Plugins

## Zusammenspiel mit WordPress

Der Booking Assistant nutzt die API als primäre Backend-Komponente für:

- freie Termine im Frontend
- Terminreservierungen
- Stornologik
- Rückgabe technischer und fachlicher Statusinformationen

Dadurch bleibt die geschäftslogische Terminverarbeitung zentral in der API und muss nicht dupliziert in WordPress gepflegt werden.

## Aktueller Status

Die API bleibt zentrales Backend-System fuer Slot-Suche, Reservierungen und Sync-Logik. Fuer den aktuellen Stand wurde ein operativer Smoke-Test-Workflow ergänzt.

## Releases

- [Release 1.2.3](Release-1.2.3)
- [Release 1.2.2](Release-1.2.2)