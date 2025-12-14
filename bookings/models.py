from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Tuple

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


def get_setting(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


BOOKINGS_TENANT_MODEL = get_setting("BOOKINGS_TENANT_MODEL", None)
BOOKINGS_SERVICE_MODEL = get_setting("BOOKINGS_SERVICE_MODEL", "services.Service")
BOOKINGS_PROVIDER_MODEL = get_setting("BOOKINGS_PROVIDER_MODEL", "providers.Provider")
BOOKINGS_ADDON_MODEL = get_setting("BOOKINGS_ADDON_MODEL", "services.ServiceAddon")
BOOKINGS_USER_MODEL = get_setting("BOOKINGS_USER_MODEL", settings.AUTH_USER_MODEL)
BOOKINGS_SLOT_VALIDATION_MODE = get_setting("BOOKINGS_SLOT_VALIDATION_MODE", "ENGINE")
BOOKINGS_SLOTS_AVAILABLE_FUNC = get_setting(
    "BOOKINGS_SLOTS_AVAILABLE_FUNC", "slots.selectors.list_available_slots"
)
BOOKINGS_DUPLICATE_GUARD_MINUTES = int(
    get_setting("BOOKINGS_DUPLICATE_GUARD_MINUTES", 0) or 0
)


TENANCY_ENABLED = bool(BOOKINGS_TENANT_MODEL)


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No show"

    ACTIVE_STATUSES: Tuple[str, str] = (Status.PENDING, Status.CONFIRMED)

    reference = models.CharField(max_length=32, unique=True, blank=True)
    if TENANCY_ENABLED:
        tenant = models.ForeignKey(
            BOOKINGS_TENANT_MODEL,
            on_delete=models.PROTECT,
            related_name="bookings",
            null=True,
            blank=True,
        )
    service = models.ForeignKey(
        BOOKINGS_SERVICE_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    provider = models.ForeignKey(
        BOOKINGS_PROVIDER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    client_name = models.CharField(max_length=255)
    client_email = models.EmailField(blank=True)
    client_phone = models.CharField(max_length=64, blank=True)
    client_user = models.ForeignKey(
        BOOKINGS_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )

    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)
    buffer_before_minutes = models.PositiveIntegerField(default=0)
    buffer_after_minutes = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    requires_approval = models.BooleanField(default=False)
    cancellation_allowed = models.BooleanField(default=True)
    cancellation_notice_minutes = models.PositiveIntegerField(default=0)
    reschedule_allowed = models.BooleanField(default=True)
    reschedule_notice_minutes = models.PositiveIntegerField(default=0)

    party_size = models.PositiveIntegerField(default=1)
    capacity_consumed = models.PositiveIntegerField(default=1)

    pricing_type = models.CharField(max_length=50, blank=True)
    price_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="TTD")

    notes_internal = models.TextField(blank=True)
    notes_client = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        BOOKINGS_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings_created",
    )

    class Meta:
        ordering = ("start_at", "id")
        indexes = [
            models.Index(fields=["provider", "start_at"]),
            models.Index(fields=["status"]),
        ]
        if TENANCY_ENABLED:
            indexes.append(models.Index(fields=["tenant", "start_at"]))

    def __str__(self) -> str:
        return self.reference

    @classmethod
    def generate_reference(cls) -> str:
        prefix = timezone.now().strftime("BK-%Y-")
        for _ in range(5):
            candidate = prefix + get_random_string(6, allowed_chars="0123456789")
            if not cls.objects.filter(reference=candidate).exists():
                return candidate
        return prefix + get_random_string(10, allowed_chars="0123456789")

    def busy_window(self) -> Tuple[datetime, datetime]:
        start = self.start_at - timedelta(minutes=self.buffer_before_minutes)
        end = self.end_at + timedelta(minutes=self.buffer_after_minutes)
        return start, end

    def clean(self) -> None:
        errors = {}

        if self.end_at and self.start_at and self.end_at <= self.start_at:
            errors["end_at"] = "End time must be after start time."
        if self.start_at and timezone.is_naive(self.start_at):
            errors["start_at"] = "Start time must be timezone-aware."
        if self.end_at and timezone.is_naive(self.end_at):
            errors["end_at"] = "End time must be timezone-aware."

        allow_multiple = False
        if self.service_id:
            allow_multiple = bool(
                getattr(self.service, "allow_multiple_clients_per_slot", False)
            )

        if not allow_multiple and self.party_size != 1:
            errors["party_size"] = (
                "Party size must be 1 for services that do not allow multiple clients per slot."
            )
        if self.capacity_consumed < self.party_size:
            errors["capacity_consumed"] = "Capacity consumed cannot be below party size."
        if not allow_multiple and self.capacity_consumed != self.party_size:
            errors["capacity_consumed"] = (
                "Capacity consumed must equal party size for single-client services."
            )

        if TENANCY_ENABLED:
            if not getattr(self, "tenant_id", None):
                errors["tenant"] = "Tenant is required when tenancy is enabled."
            else:
                related_objects = [
                    (self.service, "service"),
                    (self.provider, "provider"),
                ]
                for related_obj, label in related_objects:
                    if related_obj and hasattr(related_obj, "tenant_id"):
                        if related_obj.tenant_id != self.tenant_id:
                            errors[label] = (
                                "Tenant mismatch between booking and related object."
                            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)


class BookingAddon(models.Model):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="addons"
    )
    addon = models.ForeignKey(
        BOOKINGS_ADDON_MODEL,
        on_delete=models.PROTECT,
        related_name="booking_addons",
    )
    name_snapshot = models.CharField(max_length=255)
    extra_duration_minutes_snapshot = models.PositiveIntegerField(default=0)
    price_amount_snapshot = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency_snapshot = models.CharField(max_length=3, default="TTD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "addon"], name="unique_booking_addon"
            )
        ]

    def __str__(self) -> str:
        return f"{self.booking.reference} - {self.name_snapshot}"


class BookingEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        RESCHEDULED = "RESCHEDULED", "Rescheduled"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No show"
        NOTE_ADDED = "NOTE_ADDED", "Note added"

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    message = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    actor_user = models.ForeignKey(
        BOOKINGS_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="booking_events",
    )

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.booking.reference} - {self.event_type}"
