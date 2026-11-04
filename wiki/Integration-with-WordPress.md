# Integration with WordPress

The Restatify Booking API is the central backend service for the WordPress plugins in the Restatify stack.

## Booking Assistant

The Booking Assistant uses the API for:

- slot search
- reservation creation
- cancel token generation
- cancellation flows
- calendar-related responses

The user flow, outgoing mails, and WordPress admin configuration live inside the plugin. The core appointment logic remains centralized in the API.

## Google availability safeguards

Slot search verifies current Google availability over the search window, and reservation creation checks again immediately before writing the event. An overlapping busy interval, including an all-day busy event, must not be offered or booked.

Incomplete or malformed calendar data or failed Google access returns `503 BACKEND_UNAVAILABLE` rather than treating an unchecked calendar as free. A live booking conflict returns `409 GOOGLE_SLOT_CONFLICT`. Cron sync preserves existing busy windows when a configured source cannot be fully verified.

General calendars use Google's **Busy/Free** status, and every overlapping live FreeBusy interval blocks booking, including busy all-day events. Mark personal blockers **Busy**, especially after converting all-day events to timed events. Holiday calendars were already hard blockers through the separate paginated Events API path, regardless of transparency.

This correction must be deployed to the Booking API and sync worker; a WordPress plugin ZIP alone does not contain it. It does not prove the cause of any particular availability incident.

### Manual integration check after deployment

1. In a configured test calendar, create a **Busy** event from 15:00 to 15:30 on a day with bookable hours.
2. Before the next cron sync, request 15-minute slots: neither 15:00 nor 15:15 may be offered; 15:30 can remain available.
3. Load a free slot, then create an overlapping Google blocker before submitting the reservation. Submission must fail without a new event or confirmation.
4. Repeat with a busy all-day event, then convert it to a timed **Busy** event.
5. In a test deployment only, interrupt Google access: slot search and booking must report unavailability, not success.
6. Restore access and confirm that a genuinely free test slot still books successfully; remove the test booking afterwards.

Live verification reduces race windows but does not make changes in Google and the local database atomic.

## Benefits of this split

- clear separation of responsibilities between backend and WordPress
- less duplicated business logic
- consistent appointment processing across multiple integrations
- easier iteration on WordPress UX without duplicating backend rules

## Documentation recommendation

For the API wiki, a compact structure is usually enough:

- product overview
- integration overview
- endpoint documentation
- release history only when real API changes are introduced