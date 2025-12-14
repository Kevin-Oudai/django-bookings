from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import TestCase

from bookings.models import Booking
from bookings.selectors import get_busy_intervals
from bookings.services import create_booking
from bookings.tests.testapp.models import Provider, Service


class SelectorTests(TestCase):
    def setUp(self) -> None:
        self.provider = Provider.objects.create(name="Provider B")
        self.service = Service.objects.create(name="Service B", duration_minutes=60)
        self.window_start = datetime(2025, 1, 2, 8, 0, tzinfo=dt_timezone.utc)

    def test_busy_intervals_include_buffers_for_active_statuses(self):
        booking = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.window_start,
            client_name="Alice",
        )
        booking.buffer_before_minutes = 10
        booking.buffer_after_minutes = 5
        booking.save(update_fields=["buffer_before_minutes", "buffer_after_minutes"])

        cancelled = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.window_start + timedelta(hours=3),
            client_name="Bob",
        )
        cancelled.status = Booking.Status.CANCELLED
        cancelled.save(update_fields=["status"])

        intervals = get_busy_intervals(
            self.provider,
            self.window_start - timedelta(hours=1),
            self.window_start + timedelta(hours=4),
        )
        self.assertEqual(len(intervals), 1)
        start, end = intervals[0]
        self.assertEqual(
            start, booking.start_at - timedelta(minutes=booking.buffer_before_minutes)
        )
        self.assertEqual(
            end, booking.end_at + timedelta(minutes=booking.buffer_after_minutes)
        )
