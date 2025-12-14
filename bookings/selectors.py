from __future__ import annotations

from typing import List, Tuple

from .models import TENANCY_ENABLED, Booking


def get_busy_intervals(provider, start_dt, end_dt, *, tenant=None) -> List[Tuple]:
    qs = Booking.objects.filter(
        provider=provider,
        status__in=Booking.ACTIVE_STATUSES,
        start_at__lt=end_dt,
        end_at__gt=start_dt,
    )
    if TENANCY_ENABLED and tenant is not None:
        qs = qs.filter(tenant=tenant)

    intervals = []
    for booking in qs:
        intervals.append(booking.busy_window())
    return intervals
