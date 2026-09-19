from rest_framework import status, permissions, generics, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal
from datetime import date

from .models import FoodShare, ShareRequest, SavedShare
from .serializers import (
    FoodShareSerializer,
    FoodShareCreateSerializer,
    ShareRequestSerializer,
    ShareRequestCreateSerializer,
    SavedShareSerializer
)
from apps.foods.models import FoodItem
from apps.notifications.models import Notification
from apps.common.permissions import IsOwnerOrAdmin
from apps.common.utils import log_activity

class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class CommunityShareListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FoodShareSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        
        # 1. Update dynamic statuses for active shares
        active_shares = FoodShare.objects.filter(
            status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
        ).select_related('food_item')
        
        for s in active_shares:
            new_status = s.compute_status()
            if new_status != s.status:
                FoodShare.objects.filter(id=s.id).update(status=new_status)

        # 2. Base Apartment Isolation Query
        queryset = FoodShare.objects.select_related('food_item', 'owner', 'owner__apartment')

        scope = self.request.query_params.get('scope', '').strip().lower()
        
        if scope == 'mine':
            queryset = queryset.filter(owner=user)
        elif scope == 'saved':
            saved_ids = SavedShare.objects.filter(user=user).values_list('share_id', flat=True)
            queryset = queryset.filter(id__in=saved_ids)
        else:
            # Community Feed: filter by apartment isolation & active status
            if user.apartment:
                queryset = queryset.filter(
                    Q(owner__apartment=user.apartment) | Q(owner=user)
                )
            elif user.apartment_name_custom:
                queryset = queryset.filter(
                    Q(owner__apartment_name_custom__iexact=user.apartment_name_custom) | Q(owner=user)
                )

            # By default, show active non-expired shares only
            status_param = self.request.query_params.get('status', '').strip().upper()
            if status_param and status_param != 'ALL':
                queryset = queryset.filter(status=status_param)
            else:
                queryset = queryset.filter(
                    status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED],
                    quantity__gt=0
                )

        # 3. Search Filter (?search=milk)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(food_item__name__icontains=search) |
                Q(food_item__category__icontains=search)
            )

        # 4. Category Filter (?category=DAIRY)
        category = self.request.query_params.get('category', '').strip()
        if category and category != 'ALL':
            queryset = queryset.filter(food_item__category=category.upper())

        return queryset.order_by('-created_at')


class FoodShareCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FoodShareCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid share data.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            food_item_id = serializer.validated_data['food_item_id']
            food_item = FoodItem.objects.select_for_update().get(id=food_item_id, user=request.user)

            share = serializer.save(owner=request.user)

            # Update food item status to SHARED if full quantity is shared
            if food_item.quantity == share.quantity:
                food_item.status = FoodItem.Status.SHARED
                food_item.save(update_fields=['status', 'updated_at'])

            log_activity(
                user=request.user,
                action='FOOD_SHARE_CREATED',
                entity_type='FoodShare',
                entity_id=share.id,
                metadata={'food_item_id': food_item.id, 'quantity': str(share.quantity), 'title': share.title}
            )

            # Notification if user preference enabled
            if hasattr(request.user, 'settings') and request.user.settings.share_notifications:
                Notification.objects.create(
                    user=request.user,
                    food_item=food_item,
                    type=Notification.Type.SHARE_CREATED,
                    title=f"Shared: {share.title}",
                    message=f"Your share for {share.quantity} {share.unit} of {share.title} is now active in your community marketplace.",
                    priority=Notification.Priority.GOOD
                )

            return Response({
                'message': f'Successfully shared {share.quantity} {share.unit} of {share.title}.',
                'share': FoodShareSerializer(share, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)


class FoodShareDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FoodShareSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return FoodShare.objects.all()

    def delete(self, request, *args, **kwargs):
        share = self.get_object()
        if share.owner != request.user and request.user.role != 'ADMIN':
            return Response({'message': 'Unauthorized to cancel this share.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            share = FoodShare.objects.select_for_update().get(id=share.id)
            share.status = FoodShare.Status.CANCELLED
            share.save()

            # Cancel any pending requests
            share.requests.filter(status=ShareRequest.Status.PENDING).update(
                status=ShareRequest.Status.CANCELLED,
                updated_at=timezone.now()
            )

            # Restore food item status if it was SHARED
            if share.food_item.status == FoodItem.Status.SHARED:
                share.food_item.save() # save() recomputes status

            log_activity(
                user=request.user,
                action='FOOD_SHARE_CANCELLED',
                entity_type='FoodShare',
                entity_id=share.id,
                metadata={'title': share.title}
            )

        return Response({'message': 'Food share cancelled successfully.'}, status=status.HTTP_200_OK)


class FoodShareCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        try:
            share = FoodShare.objects.get(id=id, owner=request.user)
        except FoodShare.DoesNotExist:
            return Response({'message': 'Share not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            share = FoodShare.objects.select_for_update().get(id=share.id)
            share.status = FoodShare.Status.CANCELLED
            share.save()

            share.requests.filter(status=ShareRequest.Status.PENDING).update(
                status=ShareRequest.Status.CANCELLED,
                updated_at=timezone.now()
            )

            if share.food_item.status == FoodItem.Status.SHARED:
                share.food_item.save()

            log_activity(
                user=request.user,
                action='FOOD_SHARE_CANCELLED',
                entity_type='FoodShare',
                entity_id=share.id,
                metadata={'title': share.title}
            )

        return Response({'message': 'Share cancelled successfully.'}, status=status.HTTP_200_OK)


class ShareRequestCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        serializer = ShareRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid request data.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        requested_qty = serializer.validated_data['quantity']
        user_message = serializer.validated_data.get('message', '')

        with transaction.atomic():
            try:
                share = FoodShare.objects.select_for_update().get(id=id)
            except FoodShare.DoesNotExist:
                return Response({'message': 'Food share not found.'}, status=status.HTTP_404_NOT_FOUND)

            if share.owner == request.user:
                return Response({'message': 'You cannot request your own food share.'}, status=status.HTTP_400_BAD_REQUEST)

            if not share.is_active:
                return Response({'message': 'This food share is no longer active or available.'}, status=status.HTTP_400_BAD_REQUEST)

            if requested_qty > share.quantity:
                return Response({
                    'message': f'Cannot request {requested_qty} {share.unit}. Only {share.quantity} {share.unit} available.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Prevent duplicate active requests
            existing_req = ShareRequest.objects.filter(
                share=share,
                requester=request.user,
                status__in=[ShareRequest.Status.PENDING, ShareRequest.Status.APPROVED]
            ).exists()

            if existing_req:
                return Response({
                    'message': 'You already have an active request for this food share.'
                }, status=status.HTTP_400_BAD_REQUEST)

            req_obj = ShareRequest.objects.create(
                share=share,
                requester=request.user,
                quantity=requested_qty,
                message=user_message,
                status=ShareRequest.Status.PENDING
            )

            log_activity(
                user=request.user,
                action='SHARE_REQUEST_CREATED',
                entity_type='ShareRequest',
                entity_id=req_obj.id,
                metadata={'share_id': share.id, 'quantity': str(requested_qty)}
            )

            # Notify owner
            if hasattr(share.owner, 'settings') and share.owner.settings.share_notifications:
                Notification.objects.create(
                    user=share.owner,
                    food_item=share.food_item,
                    type=Notification.Type.SHARE_REQUEST_RECEIVED,
                    title=f"New Request: {share.title}",
                    message=f"{request.user.full_name} (Flat {request.user.flat_number}) requested {requested_qty} {share.unit} of '{share.title}'.",
                    priority=Notification.Priority.WARNING
                )

            return Response({
                'message': 'Your request has been submitted to the owner.',
                'request': ShareRequestSerializer(req_obj, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)


class ShareRequestApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        with transaction.atomic():
            try:
                req_obj = ShareRequest.objects.select_for_update().get(id=id)
            except ShareRequest.DoesNotExist:
                return Response({'message': 'Share request not found.'}, status=status.HTTP_404_NOT_FOUND)

            share = FoodShare.objects.select_for_update().get(id=req_obj.share_id)

            if share.owner != request.user:
                return Response({'message': 'Unauthorized to approve this request.'}, status=status.HTTP_403_FORBIDDEN)

            if req_obj.status != ShareRequest.Status.PENDING:
                return Response({'message': f'Request is already in {req_obj.status} state.'}, status=status.HTTP_400_BAD_REQUEST)

            if req_obj.quantity > share.quantity:
                return Response({
                    'message': f'Cannot approve request for {req_obj.quantity} {share.unit}. Only {share.quantity} {share.unit} remaining.'
                }, status=status.HTTP_400_BAD_REQUEST)

            req_obj.status = ShareRequest.Status.APPROVED
            req_obj.save()

            log_activity(
                user=request.user,
                action='SHARE_REQUEST_APPROVED',
                entity_type='ShareRequest',
                entity_id=req_obj.id,
                metadata={'requester_id': req_obj.requester_id, 'quantity': str(req_obj.quantity)}
            )

            # Notify requester
            if hasattr(req_obj.requester, 'settings') and req_obj.requester.settings.share_notifications:
                Notification.objects.create(
                    user=req_obj.requester,
                    food_item=share.food_item,
                    type=Notification.Type.SHARE_REQUEST_APPROVED,
                    title=f"Request Approved: {share.title}",
                    message=f"{request.user.full_name} approved your request for {req_obj.quantity} {share.unit} of '{share.title}'. Note: {share.pickup_note or 'Contact owner for pickup.'}",
                    priority=Notification.Priority.GOOD
                )

            return Response({
                'message': 'Request approved successfully.',
                'request': ShareRequestSerializer(req_obj, context={'request': request}).data
            }, status=status.HTTP_200_OK)


class ShareRequestRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        with transaction.atomic():
            try:
                req_obj = ShareRequest.objects.select_for_update().get(id=id)
            except ShareRequest.DoesNotExist:
                return Response({'message': 'Share request not found.'}, status=status.HTTP_404_NOT_FOUND)

            share = req_obj.share

            if share.owner != request.user:
                return Response({'message': 'Unauthorized to reject this request.'}, status=status.HTTP_403_FORBIDDEN)

            req_obj.status = ShareRequest.Status.REJECTED
            req_obj.save()

            log_activity(
                user=request.user,
                action='SHARE_REQUEST_REJECTED',
                entity_type='ShareRequest',
                entity_id=req_obj.id
            )

            if hasattr(req_obj.requester, 'settings') and req_obj.requester.settings.share_notifications:
                Notification.objects.create(
                    user=req_obj.requester,
                    food_item=share.food_item,
                    type=Notification.Type.SHARE_REQUEST_REJECTED,
                    title=f"Request Declined: {share.title}",
                    message=f"Your request for '{share.title}' was declined by the owner.",
                    priority=Notification.Priority.WARNING
                )

            return Response({'message': 'Request declined.'}, status=status.HTTP_200_OK)


class ShareRequestCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        try:
            req_obj = ShareRequest.objects.get(id=id, requester=request.user)
        except ShareRequest.DoesNotExist:
            return Response({'message': 'Share request not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

        req_obj.status = ShareRequest.Status.CANCELLED
        req_obj.save()

        log_activity(
            user=request.user,
            action='SHARE_REQUEST_CANCELLED',
            entity_type='ShareRequest',
            entity_id=req_obj.id
        )

        return Response({'message': 'Request cancelled successfully.'}, status=status.HTTP_200_OK)


class ShareRequestCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        with transaction.atomic():
            try:
                req_obj = ShareRequest.objects.select_for_update().get(id=id)
            except ShareRequest.DoesNotExist:
                return Response({'message': 'Share request not found.'}, status=status.HTTP_404_NOT_FOUND)

            share = FoodShare.objects.select_for_update().get(id=req_obj.share_id)
            food_item = FoodItem.objects.select_for_update().get(id=share.food_item_id)

            if request.user != share.owner and request.user != req_obj.requester:
                return Response({'message': 'Unauthorized to complete this request.'}, status=status.HTTP_403_FORBIDDEN)

            if req_obj.status != ShareRequest.Status.APPROVED:
                return Response({'message': 'Only approved requests can be completed.'}, status=status.HTTP_400_BAD_REQUEST)

            completed_qty = req_obj.quantity

            # 1. Update Share quantity & status
            share.quantity -= completed_qty
            if share.quantity <= Decimal('0.00'):
                share.quantity = Decimal('0.00')
                share.status = FoodShare.Status.COMPLETED
            elif share.quantity < share.initial_quantity:
                share.status = FoodShare.Status.PARTIALLY_CLAIMED

            share.save()

            # 2. Update FoodItem quantity & status
            food_item.quantity -= completed_qty
            if food_item.quantity <= Decimal('0.00'):
                food_item.quantity = Decimal('0.00')
                food_item.status = FoodItem.Status.CONSUMED

            food_item.save()

            req_obj.status = ShareRequest.Status.COMPLETED
            req_obj.save()

            log_activity(
                user=request.user,
                action='SHARE_COMPLETED',
                entity_type='ShareRequest',
                entity_id=req_obj.id,
                metadata={'completed_quantity': str(completed_qty), 'share_id': share.id}
            )

            # Notifications for both
            for u in [share.owner, req_obj.requester]:
                if hasattr(u, 'settings') and u.settings.share_notifications:
                    Notification.objects.create(
                        user=u,
                        food_item=food_item,
                        type=Notification.Type.SHARE_CLAIMED,
                        title=f"Handover Completed: {share.title}",
                        message=f"Completed sharing of {completed_qty} {share.unit} of '{share.title}'. Thank you for saving food!",
                        priority=Notification.Priority.GOOD
                    )

            return Response({
                'message': 'Share handover completed successfully!',
                'request': ShareRequestSerializer(req_obj, context={'request': request}).data
            }, status=status.HTTP_200_OK)


class SavedShareToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        try:
            share = FoodShare.objects.get(id=id)
        except FoodShare.DoesNotExist:
            return Response({'message': 'Food share not found.'}, status=status.HTTP_404_NOT_FOUND)

        saved, created = SavedShare.objects.get_or_create(user=request.user, share=share)
        if created:
            log_activity(user=request.user, action='SHARE_SAVED', entity_type='FoodShare', entity_id=share.id)
            return Response({'message': 'Share saved to favorites.', 'is_saved': True}, status=status.HTTP_201_CREATED)
        else:
            saved.delete()
            log_activity(user=request.user, action='SHARE_UNSAVED', entity_type='FoodShare', entity_id=share.id)
            return Response({'message': 'Share removed from favorites.', 'is_saved': False}, status=status.HTTP_200_OK)


class MySharesListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FoodShareSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return FoodShare.objects.filter(owner=self.request.user).order_by('-created_at')


class MyRequestsListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ShareRequestSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return ShareRequest.objects.filter(requester=self.request.user).order_by('-created_at')
