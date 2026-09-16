from django.urls import path
from .views import UserSettingsView

urlpatterns = [
    path('settings/', UserSettingsView.as_view(), name='users-settings'),
]
