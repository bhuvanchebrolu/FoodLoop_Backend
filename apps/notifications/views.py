from rest_framework import status, permissions, generics, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from .models import Notification
from .serializers import (
    NotificationSerializer, 
    AlertItemSerializer, 
    AlertSummarySerializer
)
from .services import ExpiryEngineService
from apps.foods.models import FoodItem
from apps.common.permissions import IsOwnerOrAdmin
from apps.common.utils import log_activity

class NotificationPagination(pagination.PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        unread_count = Notification.objects.filter(
            user=self.request.user, 
            is_read=False
        ).count()
        return Response({
            'count': self.page.paginator.count,
            'unread_count': unread_count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })


class NotificationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        # Trigger background check on list fetch
        ExpiryEngineService.check_and_generate_expiry_notifications(self.request.user)

        queryset = Notification.objects.filter(user=self.request.user)
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            if is_read.lower() in ['false', '0']:
                queryset = queryset.filter(is_read=False)
            elif is_read.lower() in ['true', '1']:
                queryset = queryset.filter(is_read=True)

        return queryset


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, id):
        try:
            notif = Notification.objects.get(id=id, user=request.user)
        except Notification.DoesNotExist:
            return Response({'message': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not notif.is_read:
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save()
            log_activity(
                user=request.user,
                action='NOTIFICATION_READ',
                entity_type='Notification',
                entity_id=notif.id
            )

        return Response({
            'message': 'Notification marked as read.',
            'notification': NotificationSerializer(notif).data
        }, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated_count = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).update(is_read=True, read_at=timezone.now())

        return Response({
            'message': f'Marked {updated_count} notification(s) as read.',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)


class AlertListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AlertItemSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        # Trigger expiry check engine for accuracy
        ExpiryEngineService.check_and_generate_expiry_notifications(self.request.user)

        # Retrieve active food items for user
        queryset = FoodItem.objects.filter(
            user=self.request.user,
            quantity__gt=0,
            status__in=[FoodItem.Status.AVAILABLE, FoodItem.Status.EXPIRING_SOON, FoodItem.Status.EXPIRED]
        )

        priority_param = self.request.query_params.get('priority', '').strip().upper()
        
        if priority_param == 'EXPIRED':
            queryset = queryset.filter(Q(status=FoodItem.Status.EXPIRED) | Q(expiry_date__lt=timezone.now().date()))
        elif priority_param == 'URGENT':
            queryset = queryset.filter(
                status=FoodItem.Status.EXPIRING_SOON,
                expiry_date__lte=timezone.now().date() + timezone.timedelta(days=1),
                expiry_date__gte=timezone.now().date()
            )
        elif priority_param == 'WARNING':
            queryset = queryset.filter(
                status=FoodItem.Status.EXPIRING_SOON,
                expiry_date__lte=timezone.now().date() + timezone.timedelta(days=5),
                expiry_date__gt=timezone.now().date() + timezone.timedelta(days=1)
            )
        elif priority_param == 'GOOD':
            queryset = queryset.filter(
                status=FoodItem.Status.AVAILABLE,
                expiry_date__gt=timezone.now().date() + timezone.timedelta(days=5)
            )

        return queryset.order_by('expiry_date')


class AlertSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ExpiryEngineService.check_and_generate_expiry_notifications(request.user)

        user_items = FoodItem.objects.filter(
            user=request.user,
            quantity__gt=0,
            status__in=[FoodItem.Status.AVAILABLE, FoodItem.Status.EXPIRING_SOON, FoodItem.Status.EXPIRED]
        )

        today = timezone.now().date()
        expired_count = user_items.filter(Q(status=FoodItem.Status.EXPIRED) | Q(expiry_date__lt=today)).count()
        urgent_count = user_items.filter(
            status=FoodItem.Status.EXPIRING_SOON,
            expiry_date__lte=today + timezone.timedelta(days=1),
            expiry_date__gte=today
        ).count()
        warning_count = user_items.filter(
            status=FoodItem.Status.EXPIRING_SOON,
            expiry_date__lte=today + timezone.timedelta(days=5),
            expiry_date__gt=today + timezone.timedelta(days=1)
        ).count()
        good_count = user_items.filter(
            status=FoodItem.Status.AVAILABLE,
            expiry_date__gt=today + timezone.timedelta(days=5)
        ).count()

        total_alerts = user_items.count()

        data = {
            'urgent_count': urgent_count,
            'warning_count': warning_count,
            'good_count': good_count,
            'expired_count': expired_count,
            'total_alerts': total_alerts,
        }

        serializer = AlertSummarySerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DeviceRegisterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .models import DeviceToken
        from .serializers import DeviceTokenRegisterSerializer, DeviceTokenSerializer

        serializer = DeviceTokenRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'message': 'Invalid registration data.', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        token = serializer.validated_data['token']
        device_name = serializer.validated_data.get('device_name') or 'Browser'

        # Idempotent registration: update owner and set active
        device_obj, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'device_name': device_name,
                'is_active': True
            }
        )

        log_activity(
            user=request.user,
            action='DEVICE_REGISTERED' if created else 'DEVICE_UPDATED',
            entity_type='DeviceToken',
            entity_id=device_obj.id,
            metadata={'device_name': device_name}
        )

        return Response({
            'message': 'Device registered for push notifications successfully.',
            'device': DeviceTokenSerializer(device_obj).data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class DeviceUnregisterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, id):
        from .models import DeviceToken

        try:
            device_obj = DeviceToken.objects.get(id=id, user=request.user)
        except DeviceToken.DoesNotExist:
            return Response({'message': 'Device registration not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        device_obj.is_active = False
        device_obj.save(update_fields=['is_active', 'updated_at'])

        log_activity(
            user=request.user,
            action='DEVICE_DEACTIVATED',
            entity_type='DeviceToken',
            entity_id=device_obj.id
        )

        return Response({'message': 'Device token deactivated successfully.'}, status=status.HTTP_200_OK)


class DeviceListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import DeviceToken
        from .serializers import DeviceTokenSerializer

        devices = DeviceToken.objects.filter(user=request.user, is_active=True)
        return Response({
            'count': devices.count(),
            'results': DeviceTokenSerializer(devices, many=True).data
        }, status=status.HTTP_200_OK)


class DevTestPushView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.conf import settings
        from .firebase import send_push_notification

        if not settings.DEBUG:
            return Response({'message': 'Test push endpoint is only available in DEBUG mode.'}, status=status.HTTP_403_FORBIDDEN)

        title = request.data.get('title') or "FoodLoop FCM Test 🔔"
        body = request.data.get('body') or "Firebase Web Push Notifications are working perfectly!"

        success = send_push_notification(
            user=request.user,
            title=title,
            body=body,
            data={'type': 'DEV_TEST'}
        )

        if success:
            return Response({
                'message': f"Test push notification sent successfully to active devices of {request.user.email}.",
                'success': True
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'message': "Push notification could not be delivered. Ensure you have enabled browser push notifications and Firebase environment variables are configured.",
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

