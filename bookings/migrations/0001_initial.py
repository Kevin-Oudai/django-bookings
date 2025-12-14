from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


BOOKINGS_USER_MODEL = getattr(settings, "BOOKINGS_USER_MODEL", settings.AUTH_USER_MODEL)
BOOKINGS_TENANT_MODEL = getattr(settings, "BOOKINGS_TENANT_MODEL", None)
BOOKINGS_SERVICE_MODEL = getattr(settings, "BOOKINGS_SERVICE_MODEL", "services.Service")
BOOKINGS_PROVIDER_MODEL = getattr(settings, "BOOKINGS_PROVIDER_MODEL", "providers.Provider")
BOOKINGS_ADDON_MODEL = getattr(settings, "BOOKINGS_ADDON_MODEL", "services.ServiceAddon")


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(BOOKINGS_USER_MODEL)]
    if BOOKINGS_TENANT_MODEL:
        dependencies.append(migrations.swappable_dependency(BOOKINGS_TENANT_MODEL))

    operations = [
        migrations.CreateModel(
            name="Booking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reference", models.CharField(blank=True, max_length=32, unique=True)),
                (
                    "client_name",
                    models.CharField(max_length=255),
                ),
                ("client_email", models.EmailField(blank=True, max_length=254)),
                ("client_phone", models.CharField(blank=True, max_length=64)),
                ("start_at", models.DateTimeField(db_index=True)),
                ("end_at", models.DateTimeField(db_index=True)),
                ("buffer_before_minutes", models.PositiveIntegerField(default=0)),
                ("buffer_after_minutes", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("CONFIRMED", "Confirmed"),
                            ("CANCELLED", "Cancelled"),
                            ("COMPLETED", "Completed"),
                            ("NO_SHOW", "No show"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=12,
                    ),
                ),
                ("requires_approval", models.BooleanField(default=False)),
                ("cancellation_allowed", models.BooleanField(default=True)),
                ("cancellation_notice_minutes", models.PositiveIntegerField(default=0)),
                ("reschedule_allowed", models.BooleanField(default=True)),
                ("reschedule_notice_minutes", models.PositiveIntegerField(default=0)),
                ("party_size", models.PositiveIntegerField(default=1)),
                ("capacity_consumed", models.PositiveIntegerField(default=1)),
                ("pricing_type", models.CharField(blank=True, max_length=50)),
                (
                    "price_amount",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True
                    ),
                ),
                ("currency", models.CharField(default="TTD", max_length=3)),
                ("notes_internal", models.TextField(blank=True)),
                ("notes_client", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings_created",
                        to=BOOKINGS_USER_MODEL,
                    ),
                ),
                (
                    "client_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to=BOOKINGS_USER_MODEL,
                    ),
                ),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to=BOOKINGS_PROVIDER_MODEL,
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to=BOOKINGS_SERVICE_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("start_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="BookingEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("CONFIRMED", "Confirmed"),
                            ("CANCELLED", "Cancelled"),
                            ("RESCHEDULED", "Rescheduled"),
                            ("COMPLETED", "Completed"),
                            ("NO_SHOW", "No show"),
                            ("NOTE_ADDED", "Note added"),
                        ],
                        max_length=20,
                    ),
                ),
                ("message", models.TextField(blank=True)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="booking_events",
                        to=BOOKINGS_USER_MODEL,
                    ),
                ),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="bookings.booking",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="BookingAddon",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name_snapshot", models.CharField(max_length=255)),
                (
                    "extra_duration_minutes_snapshot",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "price_amount_snapshot",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True
                    ),
                ),
                ("currency_snapshot", models.CharField(default="TTD", max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "addon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="booking_addons",
                        to=BOOKINGS_ADDON_MODEL,
                    ),
                ),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="addons",
                        to="bookings.booking",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(
                fields=["provider", "start_at"], name="bookings_provi_star_2b583c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["status"], name="bookings_status_325d43_idx"),
        ),
        migrations.AddConstraint(
            model_name="bookingaddon",
            constraint=models.UniqueConstraint(
                fields=("booking", "addon"), name="unique_booking_addon"
            ),
        ),
    ]

    if BOOKINGS_TENANT_MODEL:
        operations.insert(
            2,
            migrations.AddField(
                model_name="booking",
                name="tenant",
                field=models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="bookings",
                    to=BOOKINGS_TENANT_MODEL,
                ),
            ),
        )
        operations.insert(
            -2,
            migrations.AddIndex(
                model_name="booking",
                index=models.Index(
                    fields=["tenant", "start_at"],
                    name="bookings_tenant_start_idx",
                ),
            ),
        )
