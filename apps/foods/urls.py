from django.urls import path
from .views import (
    FoodItemListCreateView,
    FoodItemDetailView,
    FoodDashboardView
)

urlpatterns = [
    path('', FoodItemListCreateView.as_view(), name='food-list-create'),
    path('dashboard/', FoodDashboardView.as_view(), name='food-dashboard'),
    path('<int:id>/', FoodItemDetailView.as_view(), name='food-detail'),
]
