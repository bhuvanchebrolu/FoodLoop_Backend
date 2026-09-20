from rest_framework import status, generics, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Count, Sum
from decimal import Decimal

from .models import CustomUser
from .serializers import UserSerializer
from apps.apartments.models import Apartment
from apps.apartments.serializers import ApartmentSerializer
from apps.shares.models import FoodShare, ShareRequest
from apps.shares.serializers import FoodShareSerializer
from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.reports.models import Report
from apps.common.models import ActivityLog
from apps.common.permissions import IsAdmin
from apps.common.utils import log_activity

class StandardAdminPagination(pagination.PageNumberPagination):
    page_size = 15
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


class AdminDashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        total_residents = CustomUser.objects.filter(role=CustomUser.Role.RESIDENT).count()
        active_residents = CustomUser.objects.filter(role=CustomUser.Role.RESIDENT, is_active=True).count()
        total_apartments = Apartment.objects.count()
        active_shares = FoodShare.objects.filter(
            status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
        ).count()
        pending_reports = Report.objects.filter(status=Report.Status.PENDING).count()
        pending_requests = ShareRequest.objects.filter(status=ShareRequest.Status.PENDING).count()

        return Response({
            'total_residents': total_residents,
            'active_residents': active_residents,
            'total_apartments': total_apartments,
            'active_shares': active_shares,
            'pending_reports': pending_reports,
            'pending_requests': pending_requests,
        }, status=status.HTTP_200_OK)


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = UserSerializer
    pagination_class = StandardAdminPagination

    def get_queryset(self):
        queryset = CustomUser.objects.select_related('apartment').all()

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(flat_number__icontains=search)
            )

        role = self.request.query_params.get('role', '').strip().upper()
        if role and role != 'ALL':
            queryset = queryset.filter(role=role)

        active_status = self.request.query_params.get('is_active', '').strip()
        if active_status.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        elif active_status.lower() == 'false':
            queryset = queryset.filter(is_active=False)

        apartment_id = self.request.query_params.get('apartment_id', '').strip()
        if apartment_id and apartment_id != 'ALL':
            queryset = queryset.filter(apartment_id=apartment_id)

        return queryset.order_by('-created_at')


class AdminUserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, id):
        try:
            target_user = CustomUser.objects.select_related('apartment').get(id=id)
        except CustomUser.DoesNotExist:
            return Response({'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate user specific statistics
        items_added = FoodItem.objects.filter(user=target_user).count()
        consumed_count = ConsumptionRecord.objects.filter(user=target_user).count()
        wasted_count = WasteRecord.objects.filter(user=target_user).count()
        shares_created = FoodShare.objects.filter(owner=target_user).count()
        shares_completed = FoodShare.objects.filter(owner=target_user, status=FoodShare.Status.COMPLETED).count()

        recent_activity = ActivityLog.objects.filter(user=target_user)[:10]
        activity_data = [
            {
                'id': a.id,
                'action': a.action,
                'entity_type': a.entity_type,
                'created_at': a.created_at
            }
            for a in recent_activity
        ]

        return Response({
            'user': UserSerializer(target_user).data,
            'is_active': target_user.is_active,
            'stats': {
                'items_added': items_added,
                'consumed_count': consumed_count,
                'wasted_count': wasted_count,
                'shares_created': shares_created,
                'shares_completed': shares_completed,
            },
            'recent_activity': activity_data
        }, status=status.HTTP_200_OK)


class AdminUserActivateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            target_user = CustomUser.objects.get(id=id)
        except CustomUser.DoesNotExist:
            return Response({'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if target_user.is_active:
            return Response({'message': 'This account is already active.'}, status=status.HTTP_400_BAD_REQUEST)

        target_user.is_active = True
        target_user.save()

        log_activity(
            user=request.user,
            action='ADMIN_USER_ACTIVATED',
            entity_type='User',
            entity_id=target_user.id,
            metadata={'target_email': target_user.email}
        )

        return Response({
            'message': f'Account for {target_user.email} has been activated.',
            'user': UserSerializer(target_user).data
        }, status=status.HTTP_200_OK)


class AdminUserDeactivateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            target_user = CustomUser.objects.get(id=id)
        except CustomUser.DoesNotExist:
            return Response({'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not target_user.is_active:
            return Response({'message': 'This account is already inactive.'}, status=status.HTTP_400_BAD_REQUEST)

        if target_user == request.user:
            return Response({'message': 'You cannot deactivate your own administrative account.'}, status=status.HTTP_400_BAD_REQUEST)

        target_user.is_active = False
        target_user.save()

        log_activity(
            user=request.user,
            action='ADMIN_USER_DEACTIVATED',
            entity_type='User',
            entity_id=target_user.id,
            metadata={'target_email': target_user.email}
        )

        return Response({
            'message': f'Account for {target_user.email} has been deactivated.',
            'user': UserSerializer(target_user).data
        }, status=status.HTTP_200_OK)


class AdminUserRoleView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            target_user = CustomUser.objects.get(id=id)
        except CustomUser.DoesNotExist:
            return Response({'message': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_role = request.data.get('role', '').strip().upper()
        if new_role not in [CustomUser.Role.RESIDENT, CustomUser.Role.ADMIN]:
            return Response({'message': 'Invalid role. Must be RESIDENT or ADMIN.'}, status=status.HTTP_400_BAD_REQUEST)

        if target_user.role == new_role:
            return Response({'message': f'User is already assigned the {new_role} role.'}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent demoting the last active administrator
        if target_user.role == CustomUser.Role.ADMIN and new_role != CustomUser.Role.ADMIN:
            admin_count = CustomUser.objects.filter(role=CustomUser.Role.ADMIN, is_active=True).count()
            if admin_count <= 1:
                return Response({
                    'message': 'Cannot demote the sole active administrator. System must have at least one active admin.'
                }, status=status.HTTP_400_BAD_REQUEST)

        old_role = target_user.role
        target_user.role = new_role
        target_user.save()

        log_activity(
            user=request.user,
            action='ADMIN_ROLE_CHANGED',
            entity_type='User',
            entity_id=target_user.id,
            metadata={'target_email': target_user.email, 'old_role': old_role, 'new_role': new_role}
        )

        return Response({
            'message': f'User role for {target_user.email} changed from {old_role} to {new_role}.',
            'user': UserSerializer(target_user).data
        }, status=status.HTTP_200_OK)


class AdminApartmentListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        apartments = Apartment.objects.all().order_by('name')
        results = []
        for apt in apartments:
            resident_count = CustomUser.objects.filter(apartment=apt, is_active=True).count()
            active_shares_count = FoodShare.objects.filter(
                owner__apartment=apt,
                status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
            ).count()
            apt_data = ApartmentSerializer(apt).data
            apt_data['resident_count'] = resident_count
            apt_data['active_shares_count'] = active_shares_count
            results.append(apt_data)

        return Response(results, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ApartmentSerializer(data=request.data)
        if serializer.is_valid():
            apt = serializer.save()
            log_activity(
                user=request.user,
                action='ADMIN_APARTMENT_CREATED',
                entity_type='Apartment',
                entity_id=apt.id,
                metadata={'name': apt.name}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response({'message': 'Invalid apartment data.', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class AdminApartmentDetailView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, id):
        try:
            apt = Apartment.objects.get(id=id)
        except Apartment.DoesNotExist:
            return Response({'message': 'Apartment not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ApartmentSerializer(apt, data=request.data, partial=True)
        if serializer.is_valid():
            apt = serializer.save()
            log_activity(
                user=request.user,
                action='ADMIN_APARTMENT_UPDATED',
                entity_type='Apartment',
                entity_id=apt.id
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({'message': 'Unable to update apartment.', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class AdminShareListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = FoodShareSerializer
    pagination_class = StandardAdminPagination

    def get_queryset(self):
        queryset = FoodShare.objects.select_related('food_item', 'owner', 'owner__apartment').all()

        status_param = self.request.query_params.get('status', '').strip().upper()
        if status_param and status_param != 'ALL':
            queryset = queryset.filter(status=status_param)

        apartment_id = self.request.query_params.get('apartment_id', '').strip()
        if apartment_id and apartment_id != 'ALL':
            queryset = queryset.filter(owner__apartment_id=apartment_id)

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(owner__full_name__icontains=search) |
                Q(owner__email__icontains=search)
            )

        return queryset.order_by('-created_at')


class AdminShareModerateView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            share = FoodShare.objects.get(id=id)
        except FoodShare.DoesNotExist:
            return Response({'message': 'Food share not found.'}, status=status.HTTP_404_NOT_FOUND)

        reason = request.data.get('reason', 'Moderated by administrator.')

        with transaction.atomic():
            share.status = FoodShare.Status.CANCELLED
            share.save()

            share.requests.filter(status=ShareRequest.Status.PENDING).update(
                status=ShareRequest.Status.CANCELLED
            )

            log_activity(
                user=request.user,
                action='SHARE_MODERATED',
                entity_type='FoodShare',
                entity_id=share.id,
                metadata={'reason': reason, 'title': share.title}
            )

        return Response({
            'message': f"Food share '{share.title}' has been cancelled by moderator.",
            'share': FoodShareSerializer(share).data
        }, status=status.HTTP_200_OK)


class AdminSystemActivityView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    pagination_class = StandardAdminPagination

    def list(self, request, *args, **kwargs):
        queryset = ActivityLog.objects.select_related('user').all()

        action = request.query_params.get('action', '').strip()
        if action:
            queryset = queryset.filter(action__icontains=action)

        entity_type = request.query_params.get('entity_type', '').strip()
        if entity_type:
            queryset = queryset.filter(entity_type__icontains=entity_type)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search) |
                Q(user__full_name__icontains=search) |
                Q(action__icontains=search)
            )

        page = self.paginate_queryset(queryset.order_by('-created_at'))
        data = [
            {
                'id': a.id,
                'user_email': a.user.email if a.user else 'System',
                'user_name': a.user.full_name if a.user else 'System',
                'action': a.action,
                'entity_type': a.entity_type,
                'entity_id': a.entity_id,
                'metadata': a.metadata,
                'created_at': a.created_at
            }
            for a in page
        ]
        return self.get_paginated_response(data)
