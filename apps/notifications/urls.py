from django.urls import path
from .views import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    AlertListView,
    AlertSummaryView,
    DeviceRegisterView,
    DeviceUnregisterView,
    DeviceListView,
    DevTestPushView
)

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:id>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/read-all/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('alerts/', AlertListView.as_view(), name='alert-list'),
    path('alerts/summary/', AlertSummaryView.as_view(), name='alert-summary'),
    path('devices/register/', DeviceRegisterView.as_view(), name='device-register'),
    path('devices/<int:id>/', DeviceUnregisterView.as_view(), name='device-unregister'),
    path('devices/', DeviceListView.as_view(), name='device-list'),
    path('dev/test-push/', DevTestPushView.as_view(), name='dev-test-push'),
]

