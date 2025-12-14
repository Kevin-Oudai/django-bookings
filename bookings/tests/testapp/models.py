from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=64)

    def __str__(self) -> str:
        return self.name


class Service(models.Model):
    name = models.CharField(max_length=100)
    duration_minutes = models.PositiveIntegerField(default=60)
    allow_multiple_clients_per_slot = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    cancellation_allowed = models.BooleanField(default=True)
    cancellation_notice_minutes = models.PositiveIntegerField(default=0)
    reschedule_allowed = models.BooleanField(default=True)
    reschedule_notice_minutes = models.PositiveIntegerField(default=0)
    pricing_type = models.CharField(max_length=20, blank=True)
    price_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="TTD")
    tenant = models.ForeignKey(
        "testapp.Tenant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="services",
    )

    def __str__(self) -> str:
        return self.name


class Provider(models.Model):
    name = models.CharField(max_length=100)
    tenant = models.ForeignKey(
        "testapp.Tenant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="providers",
    )

    def __str__(self) -> str:
        return self.name


class ServiceAddon(models.Model):
    name = models.CharField(max_length=100)
    extra_duration_minutes = models.PositiveIntegerField(default=0)
    price_amount = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="TTD")

    def __str__(self) -> str:
        return self.name
