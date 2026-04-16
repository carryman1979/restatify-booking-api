Restatify Booking API: current local changes on main

- Version bump from 1.1.x to 1.2.0 in FastAPI metadata and README.
- Added cancellation data to the reservation model, including cancel token, cancellation reason/message, cancelled timestamp, and stored Google event metadata.
- Added runtime schema migration support so existing databases receive the new cancellation-related columns and indexes automatically on startup.
- Extended reservation creation to generate cancel tokens and persist Google Calendar event identifiers returned by event creation.
- Added `POST /v1/reservations/cancel` with repeat-cancel handling, reservation status transition to `cancelled`, and structured response payload for the WordPress plugin.
- Added Google Calendar event deletion on cancellation when stored calendar and event identifiers are available.
- Hardened Google FreeBusy live-conflict checks so inaccessible configured calendars block booking instead of risking overbooking.
- Hardened the sync worker so inaccessible configured calendars abort sync and preserve existing busy blocks.
- Added release documentation and cleaned release packaging for the 1.2.0 artifact.