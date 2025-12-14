from __future__ import annotations

import importlib
from datetime import timedelta
from typing import Iterable, List, Optional, Sequence

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    BOOKINGS_ADDON_MODEL,
    TENANCY_ENABLED,
    Booking,
    BookingAddon,
    BookingEvent,
)


def _load_model(path: str):
    return apps.get_model(path)


def _load_slots_available_func():
    func_path = getattr(
        settings, "BOOKINGS_SLOTS_AVAILABLE_FUNC", "slots.selectors.list_available_slots"
    )
    module_path, func_name = func_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def _calculate_total_duration_minutes(service, addons: Sequence) -> int:
    base_duration = getattr(service, "duration_minutes", None)
    if base_duration is None:
        raise ValidationError("Service is missing duration_minutes.")
    total = int(base_duration)
    for addon in addons:
        total += int(getattr(addon, "extra_duration_minutes", 0))
    return total


def _validate_slot_availability(
    service,
    provider,
    start_at,
    end_at,
    tenant=None,
):
    validation_mode = getattr(settings, "BOOKINGS_SLOT_VALIDATION_MODE", "ENGINE")
    if validation_mode != "ENGINE":
        return
    slots_func = _load_slots_available_func()
    available_slots = slots_func(
        service=service,
        provider=provider,
        start_dt=start_at,
        end_dt=end_at,
        tenant=tenant,
    )
    if start_at not in available_slots:
        raise ValidationError("Selected start time is not available for this service.")


def _check_duplicate_guard(service, provider, start_at, tenant=None):
    guard_minutes = int(getattr(settings, "BOOKINGS_DUPLICATE_GUARD_MINUTES", 0) or 0)
    if not guard_minutes:
        return
    window_start = start_at - timedelta(minutes=guard_minutes)
    window_end = start_at + timedelta(minutes=guard_minutes)
    qs = Booking.objects.filter(
        provider=provider,
        service=service,
        start_at__gte=window_start,
        start_at__lte=window_end,
        status__in=Booking.ACTIVE_STATUSES,
    )
    if TENANCY_ENABLED and tenant is not None:
        qs = qs.filter(tenant=tenant)
    if qs.exists():
        raise ValidationError(
            "A similar booking already exists within the duplicate guard window."
        )


def _check_overlaps(
    provider,
    start_at,
    end_at,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
    tenant=None,
    exclude_booking_id: Optional[int] = None,
):
    new_start = start_at - timedelta(minutes=buffer_before_minutes)
    new_end = end_at + timedelta(minutes=buffer_after_minutes)

    qs = Booking.objects.select_for_update().filter(
        provider=provider, status__in=Booking.ACTIVE_STATUSES
    )
    if exclude_booking_id:
        qs = qs.exclude(pk=exclude_booking_id)
    if TENANCY_ENABLED and tenant is not None:
        qs = qs.filter(tenant=tenant)

    conflicts = []
    for existing in qs:
        busy_start, busy_end = existing.busy_window()
        if busy_start < new_end and busy_end > new_start:
            conflicts.append(existing)
    if conflicts:
        raise ValidationError("Booking conflicts with an existing booking.")


def _snapshot_service_fields(service):
    return dict(
        requires_approval=bool(getattr(service, "requires_approval", False)),
        cancellation_allowed=bool(getattr(service, "cancellation_allowed", True)),
        cancellation_notice_minutes=int(
            getattr(service, "cancellation_notice_minutes", 0) or 0
        ),
        reschedule_allowed=bool(getattr(service, "reschedule_allowed", True)),
        reschedule_notice_minutes=int(
            getattr(service, "reschedule_notice_minutes", 0) or 0
        ),
        pricing_type=getattr(service, "pricing_type", "") or "",
        price_amount=getattr(service, "price_amount", None),
        currency=getattr(service, "currency", "TTD") or "TTD",
    )


def _create_booking_addons(booking: Booking, addons) -> None:
    for addon in addons:
        BookingAddon.objects.create(
            booking=booking,
            addon=addon,
            name_snapshot=getattr(addon, "name", str(addon)),
            extra_duration_minutes_snapshot=int(
                getattr(addon, "extra_duration_minutes", 0) or 0
            ),
            price_amount_snapshot=getattr(addon, "price_amount", None),
            currency_snapshot=getattr(addon, "currency", "TTD") or "TTD",
        )


def create_booking(
    *,
    service,
    provider,
    start_at,
    client_name: str,
    client_email: str = "",
    client_phone: str = "",
    client_user=None,
    addon_ids: Optional[Iterable[int]] = None,
    party_size: int = 1,
    created_by=None,
    tenant=None,
    now_dt=None,
) -> Booking:
    now = now_dt or timezone.now()
    if timezone.is_naive(start_at):
        raise ValidationError("start_at must be timezone-aware.")
    addon_ids = list(addon_ids or [])

    addon_model = _load_model(BOOKINGS_ADDON_MODEL)
    addons = list(addon_model.objects.filter(id__in=addon_ids))

    total_duration = _calculate_total_duration_minutes(service, addons)
    end_at = start_at + timedelta(minutes=total_duration)
    buffer_before = int(getattr(service, "buffer_before_minutes", 0) or 0)
    buffer_after = int(getattr(service, "buffer_after_minutes", 0) or 0)

    _validate_slot_availability(service, provider, start_at, end_at, tenant=tenant)

    with transaction.atomic():
        _check_duplicate_guard(service, provider, start_at, tenant=tenant)
        _check_overlaps(
            provider=provider,
            start_at=start_at,
            end_at=end_at,
            buffer_before_minutes=buffer_before,
            buffer_after_minutes=buffer_after,
            tenant=tenant,
        )

        snapshots = _snapshot_service_fields(service)
        status = (
            Booking.Status.PENDING
            if snapshots["requires_approval"]
            else Booking.Status.CONFIRMED
        )

        booking = Booking(
            service=service,
            provider=provider,
            start_at=start_at,
            end_at=end_at,
            buffer_before_minutes=buffer_before,
            buffer_after_minutes=buffer_after,
            party_size=party_size,
            capacity_consumed=party_size,
            status=status,
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            client_user=client_user,
            created_by=created_by,
            **snapshots,
        )
        if TENANCY_ENABLED:
            booking.tenant = tenant

        booking.full_clean()
        booking.save()
        _create_booking_addons(booking, addons)
        BookingEvent.objects.create(
            booking=booking,
            event_type=BookingEvent.EventType.CREATED,
            actor_user=created_by,
            data={"status": booking.status, "created_at": now.isoformat()},
        )
        return booking


def _enforce_notice(now, target_dt, notice_minutes: int, action: str):
    if notice_minutes <= 0:
        return
    deadline = target_dt - timedelta(minutes=notice_minutes)
    if now > deadline:
        raise ValidationError(
            f"Cannot {action} within the notice window ({notice_minutes} minutes)."
        )


def cancel_booking(
    booking: Booking, *, actor=None, now_dt=None, reason: str = ""
) -> Booking:
    now = now_dt or timezone.now()
    if booking.status == Booking.Status.CANCELLED:
        return booking
    if booking.status not in Booking.ACTIVE_STATUSES:
        raise ValidationError("Only pending or confirmed bookings can be cancelled.")
    if not booking.cancellation_allowed:
        raise ValidationError("Cancellations are not allowed for this booking.")
    _enforce_notice(now, booking.start_at, booking.cancellation_notice_minutes, "cancel")

    booking.status = Booking.Status.CANCELLED
    booking.full_clean()
    booking.save(update_fields=["status", "updated_at"])
    BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.CANCELLED,
        actor_user=actor,
        message=reason,
        data={"reason": reason},
    )
    return booking


def reschedule_booking(
    booking: Booking,
    *,
    new_start_at,
    actor=None,
    addon_ids: Optional[Iterable[int]] = None,
    now_dt=None,
) -> Booking:
    now = now_dt or timezone.now()
    if timezone.is_naive(new_start_at):
        raise ValidationError("new_start_at must be timezone-aware.")
    if booking.status not in Booking.ACTIVE_STATUSES:
        raise ValidationError("Only pending or confirmed bookings can be rescheduled.")
    if not booking.reschedule_allowed:
        raise ValidationError("Rescheduling is not allowed for this booking.")
    _enforce_notice(
        now, booking.start_at, booking.reschedule_notice_minutes, "reschedule"
    )

    addon_ids = list(addon_ids) if addon_ids is not None else None
    addon_model = _load_model(BOOKINGS_ADDON_MODEL)
    if addon_ids is not None:
        addons = list(addon_model.objects.filter(id__in=addon_ids))
    else:
        addons = [addon.addon for addon in booking.addons.all()]

    total_duration = _calculate_total_duration_minutes(booking.service, addons)
    new_end_at = new_start_at + timedelta(minutes=total_duration)

    _validate_slot_availability(
        booking.service, booking.provider, new_start_at, new_end_at, tenant=getattr(booking, "tenant", None)
    )

    with transaction.atomic():
        locked_booking = Booking.objects.select_for_update().get(pk=booking.pk)
        _check_overlaps(
            provider=booking.provider,
            start_at=new_start_at,
            end_at=new_end_at,
            buffer_before_minutes=locked_booking.buffer_before_minutes,
            buffer_after_minutes=locked_booking.buffer_after_minutes,
            tenant=getattr(locked_booking, "tenant", None),
            exclude_booking_id=locked_booking.pk,
        )

        locked_booking.start_at = new_start_at
        locked_booking.end_at = new_end_at
        locked_booking.full_clean()
        locked_booking.save(update_fields=["start_at", "end_at", "updated_at"])

        if addon_ids is not None:
            locked_booking.addons.all().delete()
            _create_booking_addons(locked_booking, addons)

        BookingEvent.objects.create(
            booking=locked_booking,
            event_type=BookingEvent.EventType.RESCHEDULED,
            actor_user=actor,
            data={
                "new_start_at": new_start_at.isoformat(),
                "new_end_at": new_end_at.isoformat(),
            },
        )
        return locked_booking


def complete_booking(booking: Booking, *, actor=None) -> Booking:
    if booking.status == Booking.Status.CANCELLED:
        raise ValidationError("Cancelled bookings cannot be completed.")
    if booking.status == Booking.Status.COMPLETED:
        return booking
    booking.status = Booking.Status.COMPLETED
    booking.full_clean()
    booking.save(update_fields=["status", "updated_at"])
    BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.COMPLETED,
        actor_user=actor,
    )
    return booking


def mark_no_show(booking: Booking, *, actor=None) -> Booking:
    if booking.status == Booking.Status.CANCELLED:
        raise ValidationError("Cancelled bookings cannot be marked as no-show.")
    if booking.status == Booking.Status.NO_SHOW:
        return booking
    booking.status = Booking.Status.NO_SHOW
    booking.full_clean()
    booking.save(update_fields=["status", "updated_at"])
    BookingEvent.objects.create(
        booking=booking,
        event_type=BookingEvent.EventType.NO_SHOW,
        actor_user=actor,
    )
    return booking
