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