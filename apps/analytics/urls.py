from django.urls import path
from .views import (
    AnalyticsOverviewView,
    AnalyticsConsumptionView,
    AnalyticsWasteView,
    AnalyticsSharingView,
    AnalyticsImpactView
)

urlpatterns = [
    path('overview/', AnalyticsOverviewView.as_view(), name='analytics-overview'),
    path('consumption/', AnalyticsConsumptionView.as_view(), name='analytics-consumption'),
    path('waste/', AnalyticsWasteView.as_view(), name='analytics-waste'),
    path('sharing/', AnalyticsSharingView.as_view(), name='analytics-sharing'),
    path('impact/', AnalyticsImpactView.as_view(), name='analytics-impact'),
]
