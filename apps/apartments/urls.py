from django.urls import path
from .views import ApartmentListView

urlpatterns = [
    path('', ApartmentListView.as_view(), name='apartment-list'),
]
