from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

STARTING_BALANCE = Decimal("10000.00")


class UserProfile(models.Model):
    """Per-user wallet. `balance` is spendable money: the amount of a user's
    current leading bids is already deducted ("frozen") from it."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=STARTING_BALANCE)

    def __str__(self):
        return f"{self.user} ({self.balance})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class Lot(models.Model):
    """A single galactic artifact up for auction."""

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    starting_price = models.DecimalField(max_digits=12, decimal_places=2)
    current_highest_bid = models.DecimalField(max_digits=12, decimal_places=2)
    current_winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="winning_lots",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_lots",
    )
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Bid(models.Model):
    """A single bid placed on a lot."""

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="bids")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bids",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bid {self.amount} on {self.lot}"
