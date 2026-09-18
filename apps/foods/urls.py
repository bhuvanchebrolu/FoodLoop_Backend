from django.urls import path
from .views import (
    FoodItemListCreateView,
    FoodItemDetailView,
    FoodDashboardView,
    ConsumeFoodView,
    WasteFoodView,
    ConsumptionHistoryView,
    WasteHistoryView
)

urlpatterns = [
    path('', FoodItemListCreateView.as_view(), name='food-list-create'),
    path('dashboard/', FoodDashboardView.as_view(), name='food-dashboard'),
    path('<int:id>/', FoodItemDetailView.as_view(), name='food-detail'),
    path('<int:id>/consume/', ConsumeFoodView.as_view(), name='food-consume'),
    path('<int:id>/waste/', WasteFoodView.as_view(), name='food-waste'),
    path('<int:id>/consumption/', ConsumptionHistoryView.as_view(), name='food-item-consumption'),
    path('<int:id>/waste-history/', WasteHistoryView.as_view(), name='food-item-waste'),
]
