# mroudai-django-bookings

`django-bookings` is a reusable Django app for creating and managing appointment bookings with a simple, opinionated lifecycle. It focuses on storing bookings safely and integrating with an external slots/availability engine.

## What it does
- Booking model with lifecycle (`PENDING`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`)
- Concurrency-safe creation and rescheduling with overlap protection and optional duplicate guard window
- Optional tenancy scope and snapshots of cancellation/reschedule rules from the service
- Add-on snapshots and optional booking events for audit history
- Busy-interval selector compatible with `django-slots`

## What it does **not** do
- Payment processing
- Notifications
- Availability logic (relies on your slots engine)
- End-user UI (admin is provided)

## Installation
1. Add to `INSTALLED_APPS`:
   ```python
   INSTALLED_APPS = [
       # ...
       "bookings",
   ]
   ```
2. Configure the settings below as needed.
3. Run migrations: `python manage.py migrate`.

## Settings (defaults)
```python
BOOKINGS_TENANT_MODEL = None  # e.g. "tenants.Tenant"
BOOKINGS_SERVICE_MODEL = "services.Service"
BOOKINGS_PROVIDER_MODEL = "providers.Provider"
BOOKINGS_ADDON_MODEL = "services.ServiceAddon"
BOOKINGS_USER_MODEL = None  # defaults to settings.AUTH_USER_MODEL

# Slot validation
BOOKINGS_SLOT_VALIDATION_MODE = "ENGINE"  # or "NONE"
BOOKINGS_SLOTS_AVAILABLE_FUNC = "slots.selectors.list_available_slots"

# Optional duplicate guard (minutes)
BOOKINGS_DUPLICATE_GUARD_MINUTES = 0
```

### Tenancy
If `BOOKINGS_TENANT_MODEL` is set, bookings include a tenant FK and must match the tenant of referenced service/provider when those models expose `tenant_id`.

### Slots integration
When `BOOKINGS_SLOT_VALIDATION_MODE="ENGINE"`, `create_booking` and `reschedule_booking` call `BOOKINGS_SLOTS_AVAILABLE_FUNC(service, provider, start_dt, end_dt, tenant=None)` and require the chosen `start_at` to be present in the returned list. Set this to your slots selector.

Expose busy intervals to `django-slots` with:
```python
from bookings.selectors import get_busy_intervals
```
It returns buffered busy windows for bookings in `PENDING`/`CONFIRMED`.

## Service-layer API
```python
from bookings.services import (
    create_booking,
    cancel_booking,
    reschedule_booking,
    complete_booking,
    mark_no_show,
)
```
- `create_booking` snapshots service rules, validates availability (when enabled), prevents overlaps, and records a `CREATED` event.
- `cancel_booking` / `reschedule_booking` enforce notice windows stored on the booking.
- `complete_booking` and `mark_no_show` transition status and log events.

All business-rule failures raise `django.core.exceptions.ValidationError`.

## Concurrency and overlap protection
- Application-level overlap detection using `select_for_update()` during create/reschedule.
- Buffers (`buffer_before_minutes`/`buffer_after_minutes`) are included in busy-window checks.
- Optional `BOOKINGS_DUPLICATE_GUARD_MINUTES` rejects near-identical duplicates.

## Admin
The Django admin lists bookings with filters/search, includes inline add-ons/events, and enforces `full_clean()` on save.

## Running tests
```
python test bookings
```
The helper script defaults to `bookings.tests.settings`; pass additional labels/paths after `test` as needed.

## Publishing
Use the helper scripts to build and upload (expects PyPI credentials via `~/.pypirc` or `PYPI_USERNAME`/`PYPI_PASSWORD`):
- Bash: `bash publish.sh`
- Python: `python upload project`

SQLite is used in tests; PostgreSQL is recommended in production (consider adding an exclusion constraint for overlaps there).
