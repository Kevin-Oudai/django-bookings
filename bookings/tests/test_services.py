from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from bookings.services import (
    cancel_booking,
    complete_booking,
    create_booking,
    mark_no_show,
    reschedule_booking,
)
from bookings.tests.testapp.models import Provider, Service, ServiceAddon


def fake_slots_available(*, service, provider, start_dt, end_dt, tenant=None):
    """Stub slot selector that returns no matching slots."""
    return []


def permissive_slots_available(*, service, provider, start_dt, end_dt, tenant=None):
    return [start_dt]


class BookingServiceTests(TestCase):
    def setUp(self) -> None:
        self.provider = Provider.objects.create(name="Provider A")
        self.service = Service.objects.create(name="Service A", duration_minutes=60)
        self.start = datetime(2025, 1, 1, 9, 0, tzinfo=dt_timezone.utc)

    def test_create_booking_status_based_on_requires_approval(self):
        booking = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start,
            client_name="Alice",
        )
        self.assertEqual(booking.status, booking.Status.CONFIRMED)

        approval_service = Service.objects.create(
            name="Needs approval", duration_minutes=60, requires_approval=True
        )
        booking_pending = create_booking(
            service=approval_service,
            provider=self.provider,
            start_at=self.start + timedelta(hours=2),
            client_name="Bob",
        )
        self.assertEqual(booking_pending.status, booking_pending.Status.PENDING)

    def test_end_time_computed_with_addons(self):
        addon = ServiceAddon.objects.create(
            name="Extra time", extra_duration_minutes=30, price_amount=50
        )
        booking = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start,
            addon_ids=[addon.id],
            client_name="Charlie",
        )
        expected_end = self.start + timedelta(minutes=90)
        self.assertEqual(booking.end_at, expected_end)
        self.assertEqual(booking.addons.count(), 1)
        addon_row = booking.addons.first()
        self.assertEqual(addon_row.extra_duration_minutes_snapshot, 30)

    def test_prevent_overlapping_bookings(self):
        create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start,
            client_name="Dave",
        )
        with self.assertRaises(ValidationError):
            create_booking(
                service=self.service,
                provider=self.provider,
                start_at=self.start + timedelta(minutes=30),
                client_name="Eve",
            )

    def test_prevent_overlap_on_reschedule(self):
        first = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start,
            client_name="Fiona",
        )
        second = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start + timedelta(hours=2),
            client_name="Gary",
        )
        with self.assertRaises(ValidationError):
            reschedule_booking(
                second, new_start_at=self.start + timedelta(minutes=15)
            )
        # reschedule to a free slot succeeds
        updated = reschedule_booking(
            second, new_start_at=self.start + timedelta(hours=3)
        )
        self.assertEqual(updated.start_at, self.start + timedelta(hours=3))

    @override_settings(
        BOOKINGS_SLOT_VALIDATION_MODE="ENGINE",
        BOOKINGS_SLOTS_AVAILABLE_FUNC="bookings.tests.test_services.fake_slots_available",
    )
    def test_slot_validation_rejects_missing_slot(self):
        with self.assertRaises(ValidationError):
            create_booking(
                service=self.service,
                provider=self.provider,
                start_at=self.start + timedelta(hours=1),
                client_name="Hank",
            )

    @override_settings(
        BOOKINGS_SLOT_VALIDATION_MODE="ENGINE",
        BOOKINGS_SLOTS_AVAILABLE_FUNC="bookings.tests.test_services.permissive_slots_available",
    )
    def test_slot_validation_allows_listed_slot(self):
        booking = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start,
            client_name="Ivy",
        )
        self.assertEqual(booking.start_at, self.start)

    def test_cancellation_notice_enforced(self):
        notice_service = Service.objects.create(
            name="Cancelable",
            duration_minutes=30,
            cancellation_allowed=True,
            cancellation_notice_minutes=60,
        )
        booking = create_booking(
            service=notice_service,
            provider=self.provider,
            start_at=self.start,
            client_name="Ivan",
        )
        with self.assertRaises(ValidationError):
            cancel_booking(
                booking,
                now_dt=self.start - timedelta(minutes=30),
                reason="Too late",
            )

    def test_reschedule_notice_enforced(self):
        notice_service = Service.objects.create(
            name="Reschedule",
            duration_minutes=45,
            reschedule_allowed=True,
            reschedule_notice_minutes=90,
        )
        booking = create_booking(
            service=notice_service,
            provider=self.provider,
            start_at=self.start,
            client_name="Jane",
        )
        with self.assertRaises(ValidationError):
            reschedule_booking(
                booking,
                new_start_at=self.start + timedelta(hours=1),
                now_dt=self.start - timedelta(minutes=60),
            )

    def test_complete_and_no_show_transitions(self):
        booking = create_booking(
            service=self.service,
            provider=self.provider,
            start_at=self.start,
            client_name="Kevin",
        )
        complete_booking(booking)
        self.assertEqual(booking.status, booking.Status.COMPLETED)
        mark_no_show(booking)
        self.assertEqual(booking.status, booking.Status.NO_SHOW)
