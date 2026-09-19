from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date

class FoodShare(models.Model):
    class Visibility(models.TextChoices):
        APARTMENT = 'APARTMENT', 'Apartment Residents'
        NEIGHBOURS = 'NEIGHBOURS', 'Neighbours / Community'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        PARTIALLY_CLAIMED = 'PARTIALLY_CLAIMED', 'Partially Claimed'
        CLAIMED = 'CLAIMED', 'Claimed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        EXPIRED = 'EXPIRED', 'Expired'
        COMPLETED = 'COMPLETED', 'Completed'

    food_item = models.ForeignKey(
        'foods.FoodItem',
        on_delete=models.CASCADE,
        related_name='shares'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='food_shares'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    initial_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    unit = models.CharField(max_length=20)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.APARTMENT
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True
    )
    pickup_note = models.TextField(blank=True, default='')
    expires_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Food Share'
        verbose_name_plural = 'Food Shares'
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['visibility', 'status']),
            models.Index(fields=['food_item', 'status']),
        ]

    def compute_status(self):
        """
        Calculates share status dynamically based on quantity and expiration dates.
        """
        if self.status in [self.Status.CANCELLED, self.Status.COMPLETED]:
            return self.status

        today = date.today()
        share_expired = (self.expires_at and self.expires_at < today) or (self.food_item.expiry_date < today)
        
        if share_expired:
            return self.Status.EXPIRED

        if self.quantity <= 0:
            return self.Status.CLAIMED
        elif self.quantity < self.initial_quantity:
            return self.Status.PARTIALLY_CLAIMED
        else:
            return self.Status.AVAILABLE

    def save(self, *args, **kwargs):
        self.status = self.compute_status()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        today = date.today()
        return (self.expires_at and self.expires_at < today) or (self.food_item.expiry_date < today)

    @property
    def is_active(self):
        return self.status in [self.Status.AVAILABLE, self.Status.PARTIALLY_CLAIMED] and self.quantity > 0 and not self.is_expired

    def __str__(self):
        return f"{self.title} ({self.quantity} {self.unit}) by {self.owner.email} [{self.status}]"


class ShareRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'
        COMPLETED = 'COMPLETED', 'Completed'

    share = models.ForeignKey(
        FoodShare,
        on_delete=models.CASCADE,
        related_name='requests'
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='share_requests'
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    message = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Share Request'
        verbose_name_plural = 'Share Requests'
        indexes = [
            models.Index(fields=['share', 'status']),
            models.Index(fields=['requester', 'status']),
        ]

    def __str__(self):
        return f"Request for {self.quantity} {self.share.unit} of {self.share.title} by {self.requester.email} [{self.status}]"


class SavedShare(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_shares'
    )
    share = models.ForeignKey(
        FoodShare,
        on_delete=models.CASCADE,
        related_name='saved_by_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Saved Share'
        verbose_name_plural = 'Saved Shares'
        constraints = [
            models.UniqueConstraint(fields=['user', 'share'], name='unique_user_saved_share')
        ]

    def __str__(self):
        return f"{self.user.email} saved share #{self.share.id} ({self.share.title})"
