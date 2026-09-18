from django.db import models
from django.conf import settings
from apps.foods.models import FoodItem

class Notification(models.Model):
    class Type(models.TextChoices):
        EXPIRY_WARNING = 'EXPIRY_WARNING', 'Expiry Warning'
        EXPIRY_URGENT = 'EXPIRY_URGENT', 'Expiry Urgent'
        FOOD_EXPIRED = 'FOOD_EXPIRED', 'Food Expired'
        SHARE_REQUEST = 'SHARE_REQUEST', 'Share Request'
        REQUEST_ACCEPTED = 'REQUEST_ACCEPTED', 'Request Accepted'
        FOOD_CLAIMED = 'FOOD_CLAIMED', 'Food Claimed'

    class Priority(models.TextChoices):
        URGENT = 'URGENT', 'Urgent'
        WARNING = 'WARNING', 'Warning'
        GOOD = 'GOOD', 'Good'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    type = models.CharField(
        max_length=30,
        choices=Type.choices,
        default=Type.EXPIRY_WARNING
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.WARNING
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'type']),
        ]

    def __str__(self):
        return f"[{self.priority}] {self.title} - {self.user.email} ({'Read' if self.is_read else 'Unread'})"
