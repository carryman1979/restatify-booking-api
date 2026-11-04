import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from fastapi import HTTPException

from app import main
from app.config import settings
from app.schemas import ReservationCreateRequest, SlotSearchRequest
from app.shared.time_utils import parse_google_busy_response
from app import sync_google_freebusy
from app.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class CalendarAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime.fromisoformat("2026-11-05T15:15:00+01:00")
        self.end = datetime.fromisoformat("2026-11-05T15:30:00+01:00")
        self.service = MagicMock()
        self.config = {
            "calendar_sources": [{"calendar_id": "test-calendar", "calendar_type": "general"}],
        }
        patches = [
            patch.object(settings, "google_credentials_json", "{}"),
            patch.object(settings, "google_calendar_ids", ""),
            patch.object(main, "load_sync_config", side_effect=lambda: self.config),
            patch.object(main.Credentials, "from_service_account_info"),
            patch.object(main, "build", return_value=self.service),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.set_busy([{
            "start": "2026-11-05T15:00:00+01:00",
            "end": "2026-11-05T15:30:00+01:00",
        }])

    def set_busy(self, busy):
        self.service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {"test-calendar": {"busy": busy}},
        }

    def assert_unavailable(self):
        with self.assertRaises(HTTPException) as raised:
            main._ensure_no_google_live_conflict(self.start, self.end)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["code"], "BACKEND_UNAVAILABLE")

    def test_1515_reservation_conflicts_with_1500_to_1530_event(self):
        with self.assertRaises(HTTPException) as raised:
            main._ensure_no_google_live_conflict(self.start, self.end)
        self.assertEqual(raised.exception.status_code, 409)

    def test_google_busy_all_day_event_also_blocks_reservation(self):
        self.set_busy([{
            "start": "2026-11-05T00:00:00+01:00",
            "end": "2026-11-06T00:00:00+01:00",
        }])
        with self.assertRaises(HTTPException) as raised:
            main._ensure_no_google_live_conflict(self.start, self.end)
        self.assertEqual(raised.exception.status_code, 409)

    def test_missing_credentials_must_not_allow_booking(self):
        with patch.object(settings, "google_credentials_json", ""):
            self.assert_unavailable()

    def test_client_initialization_failure_must_not_allow_booking(self):
        with patch.object(main, "build", side_effect=OSError("test network failure")):
            self.assert_unavailable()

    def test_transport_failure_must_not_allow_booking(self):
        self.service.freebusy.return_value.query.return_value.execute.side_effect = OSError("test timeout")
        self.assert_unavailable()

    def test_incomplete_or_invalid_google_response_must_not_mean_free(self):
        for result in [
            {}, {"calendars": {}}, {"calendars": {"test-calendar": {}}},
            {"calendars": {"test-calendar": {"busy": [], "errors": [{"reason": "notFound"}]}}},
            {"calendars": {"test-calendar": {"busy": [{"start": "bad", "end": "bad"}]}}},
            {"calendars": {"test-calendar": {"busy": [{"start": "2026-11-05T15:00:00", "end": "2026-11-05T15:30:00"}]}}},
            {"calendars": {"test-calendar": {"busy": "invalid"}}},
            [],
        ]:
            with self.subTest(result=result):
                self.service.freebusy.return_value.query.return_value.execute.return_value = result
                self.assert_unavailable()

    def test_search_does_not_offer_stale_1515_slot(self):
        request = SlotSearchRequest(
            start_iso=self.start, end_iso=self.end, duration_minutes=15, timezone="Europe/Berlin",
        )
        stale = [{"start_iso": self.start.isoformat(), "end_iso": self.end.isoformat()}]
        with patch.object(main, "search_slots", return_value=stale):
            result = main.slots_search(request, MagicMock())
        self.assertEqual(result.slots, [])

    def test_search_reports_google_failure_instead_of_showing_cached_slots(self):
        request = SlotSearchRequest(
            start_iso=self.start, end_iso=self.end, duration_minutes=15, timezone="Europe/Berlin",
        )
        with patch.object(main, "search_slots", return_value=[]):
            with patch.object(settings, "google_credentials_json", ""):
                with self.assertRaises(HTTPException) as raised:
                    main.slots_search(request, MagicMock())
        self.assertEqual(raised.exception.status_code, 503)

    def test_overlapping_reservation_does_not_create_google_event_or_save(self):
        request = ReservationCreateRequest(
            start_iso=self.start, duration_minutes=15, timezone="Europe/Berlin",
            name="Regression Test", email="test@example.com", note="",
        )
        db = MagicMock()
        stale = [{"start_iso": self.start.isoformat(), "end_iso": self.end.isoformat()}]
        with patch.object(main, "search_slots", return_value=stale):
            with patch.object(main, "_has_local_reservation_overlap", return_value=False):
                with patch.object(main, "_create_google_calendar_event") as create:
                    with self.assertRaises(HTTPException) as raised:
                        main.create_reservation(request, db)
        self.assertEqual(raised.exception.status_code, 409)
        create.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_adjacent_event_ending_at_slot_start_does_not_block(self):
        self.set_busy([{
            "start": "2026-11-05T15:00:00+01:00",
            "end": "2026-11-05T15:15:00+01:00",
        }])
        main._ensure_no_google_live_conflict(self.start, self.end)

    def test_adjacent_event_starting_at_slot_end_does_not_block(self):
        self.set_busy([{
            "start": self.end.isoformat(),
            "end": "2026-11-05T16:00:00+01:00",
        }])
        main._ensure_no_google_live_conflict(self.start, self.end)

    def test_equivalent_utc_times_block_the_same_slot(self):
        self.set_busy([{"start": "2026-11-05T14:00:00Z", "end": "2026-11-05T14:30:00Z"}])
        with self.assertRaises(HTTPException) as raised:
            main._ensure_no_google_live_conflict(self.start, self.end)
        self.assertEqual(raised.exception.status_code, 409)

    def test_genuinely_free_slot_is_still_offered(self):
        self.set_busy([])
        request = SlotSearchRequest(
            start_iso=self.start, end_iso=self.end, duration_minutes=15, timezone="Europe/Berlin",
        )
        free = [{"start_iso": self.start.isoformat(), "end_iso": self.end.isoformat()}]
        with patch.object(main, "search_slots", return_value=free):
            result = main.slots_search(request, MagicMock())
        self.assertEqual(len(result.slots), 1)

    def test_booking_failure_has_no_event_write_or_confirmation_side_effects(self):
        request = ReservationCreateRequest(
            start_iso=self.start, duration_minutes=15, timezone="Europe/Berlin",
            name="Regression Test", email="test@example.com", note="",
        )
        db = MagicMock()
        free = [{"start_iso": self.start.isoformat(), "end_iso": self.end.isoformat()}]
        with patch.object(main, "search_slots", return_value=free):
            with patch.object(main, "_has_local_reservation_overlap", return_value=False):
                with patch.object(main, "_create_google_calendar_event") as create:
                    with patch.object(settings, "google_credentials_json", ""):
                        with self.assertRaises(HTTPException) as raised:
                            main.create_reservation(request, db)
        self.assertEqual(raised.exception.status_code, 503)
        create.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_configured_calendars_are_merged_and_all_checked(self):
        with patch.object(settings, "google_calendar_ids", "env-calendar,test-calendar"):
            self.service.freebusy.return_value.query.return_value.execute.return_value = {
                "calendars": {"test-calendar": {"busy": []}, "env-calendar": {"busy": []}},
            }
            main._ensure_no_google_live_conflict(self.start, self.end)
        items = self.service.freebusy.return_value.query.call_args.kwargs["body"]["items"]
        self.assertEqual(items, [{"id": "env-calendar"}, {"id": "test-calendar"}])

    def test_missing_one_of_multiple_calendars_blocks_booking(self):
        with patch.object(settings, "google_calendar_ids", "missing-calendar"):
            self.assert_unavailable()

    def test_holiday_event_on_second_page_is_not_missed(self):
        self.config["calendar_sources"][0]["calendar_type"] = "holiday"
        self.service.events.return_value.list.return_value.execute.side_effect = [
            {"items": [], "nextPageToken": "next"},
            {"items": [{
                "start": {"date": "2026-11-05"},
                "end": {"date": "2026-11-06"},
            }]},
        ]
        with self.assertRaises(HTTPException) as raised:
            main._ensure_no_google_live_conflict(self.start, self.end)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.service.events.return_value.list.call_args.kwargs["pageToken"], "next")

    def test_holiday_access_failure_blocks_booking(self):
        self.config["calendar_sources"][0]["calendar_type"] = "holiday"
        self.service.events.return_value.list.return_value.execute.side_effect = OSError("test timeout")
        self.assert_unavailable()

    def test_incomplete_holiday_page_preserves_the_sync_cache(self):
        self.config["calendar_sources"][0]["calendar_type"] = "holiday"
        self.set_busy([])
        self.service.events.return_value.list.return_value.execute.return_value = {}
        with patch.object(sync_google_freebusy, "load_sync_config", return_value=self.config):
            with patch.object(sync_google_freebusy, "_should_run", return_value=True):
                with patch.object(sync_google_freebusy.Credentials, "from_service_account_info"):
                    with patch.object(sync_google_freebusy, "build", return_value=self.service):
                        with patch.object(sync_google_freebusy.Base.metadata, "create_all"):
                            with patch.object(sync_google_freebusy, "SessionLocal") as session:
                                with patch.object(sync_google_freebusy, "_mark_run") as mark:
                                    sync_google_freebusy.run()
        session.assert_not_called()
        mark.assert_not_called()

    def test_malformed_holiday_event_blocks_booking(self):
        self.config["calendar_sources"][0]["calendar_type"] = "holiday"
        self.service.events.return_value.list.return_value.execute.return_value = {
            "items": [{"start": ["invalid"], "end": {"date": "2026-11-06"}}],
        }
        self.assert_unavailable()

    def test_repeated_holiday_page_token_is_rejected(self):
        self.config["calendar_sources"][0]["calendar_type"] = "holiday"
        self.service.events.return_value.list.return_value.execute.return_value = {
            "items": [], "nextPageToken": "repeated",
        }
        self.assert_unavailable()
        self.assertEqual(self.service.events.return_value.list.call_count, 2)

    def test_dst_all_day_busy_ranges_are_not_exempted(self):
        for day, next_day in [
            ("2026-03-29T00:00:00+01:00", "2026-03-30T00:00:00+02:00"),
            ("2026-10-25T00:00:00+02:00", "2026-10-26T00:00:00+01:00"),
        ]:
            with self.subTest(day=day):
                self.set_busy([{"start": day, "end": next_day}])
                start = datetime.fromisoformat(day) + timedelta(hours=12)
                with self.assertRaises(HTTPException) as raised:
                    main._ensure_no_google_live_conflict(start, start + timedelta(minutes=15))
                self.assertEqual(raised.exception.status_code, 409)

    def test_missing_calendar_does_not_erase_synchronized_busy_blocks(self):
        self.service.freebusy.return_value.query.return_value.execute.return_value = {"calendars": {}}
        with patch.object(sync_google_freebusy, "load_sync_config", return_value=self.config):
            with patch.object(sync_google_freebusy, "_should_run", return_value=True):
                with patch.object(sync_google_freebusy.Credentials, "from_service_account_info"):
                    with patch.object(sync_google_freebusy, "build", return_value=self.service):
                        with patch.object(sync_google_freebusy.Base.metadata, "create_all"):
                            with patch.object(sync_google_freebusy, "SessionLocal") as session:
                                with patch.object(sync_google_freebusy, "_mark_run") as mark:
                                    sync_google_freebusy.run()
        session.assert_not_called()
        mark.assert_not_called()

    def test_explicit_free_response_is_distinct_from_missing_data(self):
        self.assertEqual(
            parse_google_busy_response({"calendars": {"test-calendar": {"busy": []}}}, ["test-calendar"]),
            {"test-calendar": []},
        )

    def test_real_slot_search_excludes_google_overlap_between_sync_runs(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        rules = [{
            "weekday": 3,
            "windows": [{"start": "15:00", "end": "16:00"}],
        }]
        self.config["availability_rules"] = rules
        request = SlotSearchRequest(
            start_iso=datetime.fromisoformat("2026-11-05T15:00:00+01:00"),
            end_iso=datetime.fromisoformat("2026-11-05T16:00:00+01:00"),
            duration_minutes=15, timezone="Europe/Berlin",
        )
        with Session(engine) as db:
            with patch("app.services.slots.load_sync_config", return_value=self.config):
                with patch.object(settings, "slot_step_minutes", 15):
                    result = main.slots_search(request, db)
        self.assertEqual(
            [slot.start_iso for slot in result.slots],
            ["2026-11-05T15:30:00+01:00", "2026-11-05T15:45:00+01:00"],
        )

    def test_real_free_reservation_still_writes_and_commits(self):
        self.set_busy([])
        engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        request = ReservationCreateRequest(
            start_iso=self.start, duration_minutes=15, timezone="Europe/Berlin",
            name="Regression Test", email="test@example.com", note="",
        )
        with Session(engine) as db:
            with patch("app.services.slots.load_sync_config", return_value=self.config):
                with patch.object(main, "_create_google_calendar_event", return_value=("event", "test-calendar")):
                    result = main.create_reservation(request, db)
        self.assertEqual(result.status, "confirmed")


if __name__ == "__main__":
    unittest.main()
