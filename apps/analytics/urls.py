from django.urls import path
from .views import (
    AnalyticsOverviewView,
    AnalyticsConsumptionView,
    AnalyticsWasteView,
    AnalyticsSharingView,
    AnalyticsImpactView,
    AnalyticsLeaderboardView,
    AnalyticsTrendsView,
    AnalyticsBadgesView
)

urlpatterns = [
    path('overview/', AnalyticsOverviewView.as_view(), name='analytics-overview'),
    path('consumption/', AnalyticsConsumptionView.as_view(), name='analytics-consumption'),
    path('waste/', AnalyticsWasteView.as_view(), name='analytics-waste'),
    path('sharing/', AnalyticsSharingView.as_view(), name='analytics-sharing'),
    path('impact/', AnalyticsImpactView.as_view(), name='analytics-impact'),
    path('leaderboard/', AnalyticsLeaderboardView.as_view(), name='analytics-leaderboard'),
    path('trends/', AnalyticsTrendsView.as_view(), name='analytics-trends'),
    path('badges/', AnalyticsBadgesView.as_view(), name='analytics-badges'),
]
