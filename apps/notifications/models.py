from django.db import models
from django.conf import settings
from apps.foods.models import FoodItem

class Notification(models.Model):
    class Type(models.TextChoices):
        EXPIRY_WARNING = 'EXPIRY_WARNING', 'Expiry Warning'
        EXPIRY_URGENT = 'EXPIRY_URGENT', 'Expiry Urgent'
        FOOD_EXPIRED = 'FOOD_EXPIRED', 'Food Expired'
        SHARE_CREATED = 'SHARE_CREATED', 'Share Created'
        SHARE_REQUEST_RECEIVED = 'SHARE_REQUEST_RECEIVED', 'Share Request Received'
        SHARE_REQUEST_APPROVED = 'SHARE_REQUEST_APPROVED', 'Share Request Approved'
        SHARE_REQUEST_REJECTED = 'SHARE_REQUEST_REJECTED', 'Share Request Rejected'
        SHARE_REQUEST_CANCELLED = 'SHARE_REQUEST_CANCELLED', 'Share Request Cancelled'
        SHARE_CLAIMED = 'SHARE_CLAIMED', 'Share Claimed'
        SHARE_CANCELLED = 'SHARE_CANCELLED', 'Share Cancelled'
        SYSTEM = 'SYSTEM', 'System Notification'

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


class DeviceToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens'
    )
    token = models.TextField(unique=True)
    device_name = models.CharField(max_length=100, blank=True, default='Browser')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'

    def __str__(self):
        return f"{self.user.email} - {self.device_name} ({'Active' if self.is_active else 'Inactive'})"


from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Notification)
def trigger_fcm_push_notification(sender, instance, created, **kwargs):
    if not created:
        return

    # Check user settings
    settings_obj = getattr(instance.user, 'settings', None)
    if settings_obj:
        if instance.type in [Notification.Type.EXPIRY_WARNING, Notification.Type.EXPIRY_URGENT, Notification.Type.FOOD_EXPIRED]:
            if not settings_obj.expiry_notifications:
                return
        elif str(instance.type).startswith('SHARE_'):
            if not settings_obj.share_notifications:
                return

    try:
        from .firebase import send_push_notification
        send_push_notification(
            user=instance.user,
            title=instance.title,
            body=instance.message,
            notification_id=instance.id,
            data={
                'type': instance.type,
                'food_item_id': str(instance.food_item_id) if instance.food_item_id else ''
            }
        )
    except Exception as exc:
        logger.warning(f"FCM post_save signal push trigger failed safely: {exc}")


