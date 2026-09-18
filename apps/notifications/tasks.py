import logging
from apps.notifications.services import ExpiryEngineService

logger = logging.getLogger(__name__)

def check_expiry_notifications_task():
    """
    Background job function for checking food expiry and generating notifications.
    Can be scheduled via Celery Beat or Django background tasks.
    """
    logger.info("Starting background check_expiry_notifications_task...")
    count = ExpiryEngineService.check_and_generate_expiry_notifications()
    logger.info(f"Finished check_expiry_notifications_task. Generated {count} notification(s).")
    return count
