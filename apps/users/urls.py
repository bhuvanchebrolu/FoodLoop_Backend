from django.urls import path
from .views import (
    RegisterView, 
    LoginView, 
    LogoutView, 
    CurrentUserView,
    ProfileView,
    ProfileSummaryView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('me/', CurrentUserView.as_view(), name='auth-me'),
    path('profile/', ProfileView.as_view(), name='auth-profile'),
    path('profile-summary/', ProfileSummaryView.as_view(), name='auth-profile-summary'),
]
