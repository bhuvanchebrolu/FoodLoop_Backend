import logging
from datetime import date, timedelta
from django.utils import timezone
from apps.foods.models import FoodItem
from apps.users.models import UserSettings
from apps.notifications.models import Notification
from apps.common.utils import log_activity

logger = logging.getLogger(__name__)

class ExpiryEngineService:
    @staticmethod
    def check_and_generate_expiry_notifications(user=None):
        """
        Scans active food items and generates idempotent expiry notifications.
        Can be run for a single user or globally across all active users.
        """
        items_qs = FoodItem.objects.filter(
            status__in=[
                FoodItem.Status.AVAILABLE,
                FoodItem.Status.EXPIRING_SOON,
                FoodItem.Status.EXPIRED
            ],
            quantity__gt=0
        ).select_related('user')

        if user:
            items_qs = items_qs.filter(user=user)

        created_count = 0
        today = date.today()
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)

        for item in items_qs:
            # 1. Always update dynamic status on FoodItem
            new_status = item.compute_status()
            if new_status != item.status:
                item.status = new_status
                item.save(update_fields=['status', 'updated_at'])

            # 2. Check user notification settings
            settings_obj, _ = UserSettings.objects.get_or_create(user=item.user)
            if not settings_obj.expiry_notifications:
                continue

            days_left = item.days_until_expiry

            # Determine Notification Type & Priority
            notif_type = None
            priority = Notification.Priority.WARNING
            title = ""
            message = ""

            if days_left < 0:
                notif_type = Notification.Type.FOOD_EXPIRED
                priority = Notification.Priority.URGENT
                title = f"Expired: {item.name}"
                message = f"Your {item.name} ({item.quantity} {item.unit}) expired {abs(days_left)} day(s) ago."
            elif days_left <= 1:
                notif_type = Notification.Type.EXPIRY_URGENT
                priority = Notification.Priority.URGENT
                title = f"Urgent Expiry: {item.name}"
                message = f"Your {item.name} ({item.quantity} {item.unit}) expires { 'today' if days_left == 0 else 'tomorrow' }!"
            elif days_left <= 5:
                notif_type = Notification.Type.EXPIRY_WARNING
                priority = Notification.Priority.WARNING
                title = f"Expiry Warning: {item.name}"
                message = f"Your {item.name} ({item.quantity} {item.unit}) expires in {days_left} days."
            else:
                continue # Food is fresh (> 5 days), no notification needed

            # 3. Idempotency Check: Prevent duplicate notification for same item & type in last 24h
            recent_duplicate = Notification.objects.filter(
                user=item.user,
                food_item=item,
                type=notif_type,
                created_at__gte=twenty_four_hours_ago
            ).exists()

            if not recent_duplicate:
                notif = Notification.objects.create(
                    user=item.user,
                    food_item=item,
                    type=notif_type,
                    title=title,
                    message=message,
                    priority=priority
                )
                created_count += 1
                log_activity(
                    user=item.user,
                    action='NOTIFICATION_CREATED',
                    entity_type='Notification',
                    entity_id=notif.id,
                    metadata={'food_item_id': item.id, 'type': notif_type}
                )

                # Attempt FCM Web Push notification delivery
                try:
                    from .firebase import send_push_notification
                    send_push_notification(
                        user=item.user,
                        title=title,
                        body=message,
                        notification_id=notif.id,
                        data={'type': notif_type, 'food_item_id': str(item.id)}
                    )
                except Exception as exc:
                    logger.warning(f"FCM push trigger exception (ignored): {exc}")

        logger.info(f"ExpiryEngine: Processed items. Generated {created_count} new notifications.")
        return created_count
