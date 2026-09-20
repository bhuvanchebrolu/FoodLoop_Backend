from django.urls import path
from .views import (
    ResidentReportCreateView,
    ResidentMyReportsView,
    AdminReportListView,
    AdminReportDetailView,
    AdminReportReviewView,
    AdminReportResolveView,
    AdminReportDismissView
)

urlpatterns = [
    # Resident endpoints
    path('', ResidentReportCreateView.as_view(), name='report-create'),
    path('my/', ResidentMyReportsView.as_view(), name='report-my'),

    # Admin endpoints
    path('admin/list/', AdminReportListView.as_view(), name='admin-report-list'),
    path('admin/<int:id>/', AdminReportDetailView.as_view(), name='admin-report-detail'),
    path('admin/<int:id>/review/', AdminReportReviewView.as_view(), name='admin-report-review'),
    path('admin/<int:id>/resolve/', AdminReportResolveView.as_view(), name='admin-report-resolve'),
    path('admin/<int:id>/dismiss/', AdminReportDismissView.as_view(), name='admin-report-dismiss'),
]
