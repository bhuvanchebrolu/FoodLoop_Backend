import os
import json
import logging
from django.conf import settings
from .models import DeviceToken

logger = logging.getLogger(__name__)

_firebase_initialized = False

def initialize_firebase_admin():
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized in app registry
        if firebase_admin._apps:
            _firebase_initialized = True
            return True

        project_id = os.getenv('FIREBASE_PROJECT_ID')
        client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
        private_key = os.getenv('FIREBASE_PRIVATE_KEY')
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        cred_json_str = os.getenv('FIREBASE_CREDENTIALS_JSON')

        cred = None

        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        elif cred_json_str:
            try:
                cred_dict = json.loads(cred_json_str)
                cred = credentials.Certificate(cred_dict)
            except Exception as e:
                logger.error(f"Failed to parse FIREBASE_CREDENTIALS_JSON: {e}")
        elif project_id and client_email and private_key:
            # Format private key line breaks if needed
            formatted_key = private_key.replace('\\n', '\n')
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": formatted_key,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(cred_dict)

        if cred:
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin SDK successfully initialized.")
            return True
        else:
            logger.info("Firebase Admin credentials not found in environment. FCM push delivery disabled.")
            return False

    except Exception as exc:
        logger.warning(f"Could not initialize Firebase Admin SDK: {exc}")
        return False


def send_push_notification(user, title, body, notification_id=None, data=None):
    """
    Sends an FCM Web Push notification to all active devices registered to `user`.
    Never raises an exception; gracefully degrades if Firebase is unconfigured or fails.
    """
    try:
        if not initialize_firebase_admin():
            return False

        from firebase_admin import messaging

        tokens_qs = DeviceToken.objects.filter(user=user, is_active=True)
        tokens_list = list(tokens_qs)

        if not tokens_list:
            return False

        token_strings = [t.token for t in tokens_list]

        # Prepare payload dictionary
        payload_data = {}
        if notification_id:
            payload_data['notification_id'] = str(notification_id)
        if data:
            for k, v in data.items():
                payload_data[str(k)] = str(v)

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=payload_data,
            tokens=token_strings,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon='/foodloop-logo.png',
                )
            )
        )

        response = messaging.send_each_for_multicast(message)

        # Process responses to deactivate invalid/unregistered tokens
        if response.failure_count > 0:
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    err = resp.exception
                    # Check if token is invalid or no longer registered
                    err_code = getattr(err, 'code', None) or str(err)
                    if 'unregistered' in str(err_code).lower() or 'invalid' in str(err_code).lower():
                        failed_token_obj = tokens_list[idx]
                        failed_token_obj.is_active = False
                        failed_token_obj.save(update_fields=['is_active', 'updated_at'])
                        logger.info(f"Deactivated invalid FCM token ID {failed_token_obj.id} for user {user.email}")

        return response.success_count > 0

    except Exception as exc:
        logger.error(f"Error delivering FCM push notification to {user.email}: {exc}")
        return False
