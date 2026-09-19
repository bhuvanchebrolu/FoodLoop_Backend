from django.urls import path
from .views import (
    CommunityShareListView,
    FoodShareCreateView,
    FoodShareDetailView,
    FoodShareCancelView,
    ShareRequestCreateView,
    ShareRequestApproveView,
    ShareRequestRejectView,
    ShareRequestCancelView,
    ShareRequestCompleteView,
    SavedShareToggleView,
    MySharesListView,
    MyRequestsListView
)

urlpatterns = [
    path('', CommunityShareListView.as_view(), name='share-list'),
    path('create/', FoodShareCreateView.as_view(), name='share-create'),
    path('my-shares/', MySharesListView.as_view(), name='my-shares'),
    path('my-requests/', MyRequestsListView.as_view(), name='my-requests'),
    path('<int:id>/', FoodShareDetailView.as_view(), name='share-detail'),
    path('<int:id>/cancel/', FoodShareCancelView.as_view(), name='share-cancel'),
    path('<int:id>/request/', ShareRequestCreateView.as_view(), name='share-request'),
    path('<int:id>/save/', SavedShareToggleView.as_view(), name='share-save'),
    path('requests/<int:id>/approve/', ShareRequestApproveView.as_view(), name='request-approve'),
    path('requests/<int:id>/reject/', ShareRequestRejectView.as_view(), name='request-reject'),
    path('requests/<int:id>/cancel/', ShareRequestCancelView.as_view(), name='request-cancel'),
    path('requests/<int:id>/complete/', ShareRequestCompleteView.as_view(), name='request-complete'),
]
