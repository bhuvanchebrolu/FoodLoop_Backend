import logging
from .models import ActivityLog

logger = logging.getLogger(__name__)

def log_activity(user, action, entity_type='', entity_id=None, metadata=None):
    """
    Helper utility to record system audit / activity logs.
    """
    if metadata is None:
        metadata = {}

    try:
        log_entry = ActivityLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not null_or_none(entity_id) else None,
            metadata=metadata
        )
        return log_entry
    except Exception as e:
        logger.error(f"Failed to log activity '{action}' for user {user}: {e}")
        return None

def null_or_none(val):
    return val is None
