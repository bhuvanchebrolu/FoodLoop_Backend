from django.urls import path
from .views_admin import (
    AdminDashboardView,
    AdminUserListView,
    AdminUserDetailView,
    AdminUserActivateView,
    AdminUserDeactivateView,
    AdminUserRoleView,
    AdminApartmentListView,
    AdminApartmentDetailView,
    AdminShareListView,
    AdminShareModerateView,
    AdminSystemActivityView
)

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('users/<int:id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('users/<int:id>/activate/', AdminUserActivateView.as_view(), name='admin-user-activate'),
    path('users/<int:id>/deactivate/', AdminUserDeactivateView.as_view(), name='admin-user-deactivate'),
    path('users/<int:id>/role/', AdminUserRoleView.as_view(), name='admin-user-role'),

    path('apartments/', AdminApartmentListView.as_view(), name='admin-apartment-list'),
    path('apartments/<int:id>/', AdminApartmentDetailView.as_view(), name='admin-apartment-detail'),

    path('shares/', AdminShareListView.as_view(), name='admin-share-list'),
    path('shares/<int:id>/moderate/', AdminShareModerateView.as_view(), name='admin-share-moderate'),

    path('activity/', AdminSystemActivityView.as_view(), name='admin-activity'),
]
