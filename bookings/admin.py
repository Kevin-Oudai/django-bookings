from django.contrib import admin

from .models import TENANCY_ENABLED, Booking, BookingAddon, BookingEvent


class BookingAddonInline(admin.TabularInline):
    model = BookingAddon
    extra = 0
    can_delete = False
    readonly_fields = (
        "addon",
        "name_snapshot",
        "extra_duration_minutes_snapshot",
        "price_amount_snapshot",
        "currency_snapshot",
        "created_at",
    )


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    can_delete = False
    readonly_fields = ("event_type", "message", "data", "created_at", "actor_user")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "provider",
        "service",
        "client_name",
        "start_at",
        "end_at",
        "status",
    )
    if TENANCY_ENABLED:
        list_display = ("reference", "tenant") + list_display[1:]

    list_filter = ("status", "provider", "service")
    if TENANCY_ENABLED:
        list_filter = ("status", "provider", "service", "tenant")

    search_fields = ("reference", "client_name", "client_email", "client_phone")
    readonly_fields = ("reference", "created_at", "updated_at")
    inlines = [BookingAddonInline, BookingEventInline]

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
