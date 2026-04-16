Restatify Booking API 1.2.0 Deploy Checklist

1. Back up the current database and the deployed API directory or image tag.
2. Extract `restatify-booking-api-1.2.0.tar.gz` on the target system.
3. Copy or keep the production environment file; do not overwrite it with example files.
4. If deploying with Docker and the image copies app code, rebuild the image before restart.
5. Start the service and verify `GET /health` responds successfully.
6. Run one reservation test and confirm a `cancel_token` is returned.
7. Run one cancellation test and confirm the reservation changes to `cancelled` and the slot becomes available again.
8. If Google write access is enabled, confirm the linked calendar event is removed on cancellation.
9. Verify the WordPress plugin can still read slots and create reservations against this API.

Rollback

1. Restore the previous API artifact or image.
2. Restore the database backup only if a rollback requires reverting persisted cancellation data.
3. Re-run health, reservation, and slot-search checks after rollback.