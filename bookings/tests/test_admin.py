from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from bookings.admin import BookingAdmin
from bookings.models import Booking
from bookings.tests.testapp.models import Provider, Service


class DummySite(AdminSite):
    pass


class BookingAdminTests(TestCase):
    def setUp(self) -> None:
        self.service = Service.objects.create(
            name="Admin Service", duration_minutes=60, allow_multiple_clients_per_slot=False
        )
        self.provider = Provider.objects.create(name="Admin Provider")
        self.admin = BookingAdmin(Booking, DummySite())
        self.request = RequestFactory().get("/")

    def test_admin_save_runs_full_clean(self):
        start = datetime(2025, 1, 3, 10, 0, tzinfo=dt_timezone.utc)
        booking = Booking(
            service=self.service,
            provider=self.provider,
            start_at=start,
            end_at=start + timedelta(minutes=60),
            party_size=2,  # invalid because service does not allow multiples
            capacity_consumed=2,
            client_name="Admin User",
            status=Booking.Status.CONFIRMED,
        )
        with self.assertRaises(ValidationError):
            self.admin.save_model(self.request, booking, form=None, change=False)
