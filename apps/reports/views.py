from rest_framework import status, permissions, generics, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction

from .models import Report
from .serializers import (
    ReportSerializer,
    ReportCreateSerializer,
    ReportResolveSerializer
)
from apps.common.permissions import IsAdmin
from apps.common.utils import log_activity
from apps.shares.models import FoodShare
from apps.users.models import CustomUser
from apps.notifications.models import Notification

class StandardResultsSetPagination(pagination.PageNumberPagination):
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


class ResidentReportCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'message': 'Failed to submit report.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        report = serializer.save(reporter=request.user)

        log_activity(
            user=request.user,
            action='REPORT_CREATED',
            entity_type='Report',
            entity_id=report.id,
            metadata={'target_type': report.target_type, 'target_id': report.target_id, 'reason': report.reason}
        )

        return Response({
            'message': 'Your report has been submitted to moderators for review.',
            'report': ReportSerializer(report).data
        }, status=status.HTTP_201_CREATED)


class ResidentMyReportsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReportSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Report.objects.filter(reporter=self.request.user).order_by('-created_at')


class AdminReportListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = ReportSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Report.objects.select_related('reporter', 'reviewed_by').all()

        status_param = self.request.query_params.get('status', '').strip().upper()
        if status_param and status_param != 'ALL':
            queryset = queryset.filter(status=status_param)

        target_type_param = self.request.query_params.get('target_type', '').strip().upper()
        if target_type_param and target_type_param != 'ALL':
            queryset = queryset.filter(target_type=target_type_param)

        reason_param = self.request.query_params.get('reason', '').strip().upper()
        if reason_param and reason_param != 'ALL':
            queryset = queryset.filter(reason=reason_param)

        return queryset.order_by('-created_at')


class AdminReportDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdmin]
    serializer_class = ReportSerializer
    queryset = Report.objects.select_related('reporter', 'reviewed_by').all()
    lookup_field = 'id'


class AdminReportReviewView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            report = Report.objects.get(id=id)
        except Report.DoesNotExist:
            return Response({'message': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        if report.status in [Report.Status.RESOLVED, Report.Status.DISMISSED]:
            return Response({'message': f'Report is already {report.status.lower()}.'}, status=status.HTTP_400_BAD_REQUEST)

        report.status = Report.Status.UNDER_REVIEW
        report.reviewed_by = request.user
        report.save()

        log_activity(
            user=request.user,
            action='REPORT_REVIEWED',
            entity_type='Report',
            entity_id=report.id
        )

        return Response({
            'message': 'Report status updated to Under Review.',
            'report': ReportSerializer(report).data
        }, status=status.HTTP_200_OK)


class AdminReportResolveView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            report = Report.objects.get(id=id)
        except Report.DoesNotExist:
            return Response({'message': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReportResolveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'message': 'Invalid resolution payload.', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data.get('action', 'NONE')
        note = serializer.validated_data.get('resolution_note', '')

        with transaction.atomic():
            # Perform soft state moderation actions if requested
            if action == 'CANCEL_SHARE' and report.target_type == Report.TargetType.FOOD_SHARE:
                try:
                    share = FoodShare.objects.select_for_update().get(id=report.target_id)
                    share.status = FoodShare.Status.CANCELLED
                    share.save()
                    log_activity(
                        user=request.user,
                        action='SHARE_MODERATED',
                        entity_type='FoodShare',
                        entity_id=share.id,
                        metadata={'reason': report.reason, 'report_id': report.id}
                    )
                except FoodShare.DoesNotExist:
                    pass

            elif action == 'DEACTIVATE_USER' and report.target_type in [Report.TargetType.USER, Report.TargetType.FOOD_SHARE]:
                target_user = None
                if report.target_type == Report.TargetType.USER:
                    target_user = CustomUser.objects.filter(id=report.target_id).first()
                elif report.target_type == Report.TargetType.FOOD_SHARE:
                    share = FoodShare.objects.filter(id=report.target_id).first()
                    if share:
                        target_user = share.owner

                if target_user and target_user.role != CustomUser.Role.ADMIN:
                    target_user.is_active = False
                    target_user.save()
                    log_activity(
                        user=request.user,
                        action='ADMIN_USER_DEACTIVATED',
                        entity_type='User',
                        entity_id=target_user.id,
                        metadata={'report_id': report.id}
                    )

            if action == 'DISMISS':
                report.status = Report.Status.DISMISSED
            else:
                report.status = Report.Status.RESOLVED

            report.reviewed_by = request.user
            report.resolution_note = note
            report.resolved_at = timezone.now()
            report.save()

            log_activity(
                user=request.user,
                action='REPORT_RESOLVED' if report.status == Report.Status.RESOLVED else 'REPORT_DISMISSED',
                entity_type='Report',
                entity_id=report.id,
                metadata={'action_taken': action, 'resolution_note': note}
            )

            # Notify reporter if enabled
            if report.reporter:
                Notification.objects.create(
                    user=report.reporter,
                    type=Notification.Type.SYSTEM,
                    title="Report Status Update",
                    message=f"Your report #{report.id} regarding {report.target_type} has been reviewed and marked as {report.status.lower()}.",
                    priority=Notification.Priority.GOOD
                )

        return Response({
            'message': f'Report successfully updated to {report.status}.',
            'report': ReportSerializer(report).data
        }, status=status.HTTP_200_OK)


class AdminReportDismissView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, id):
        try:
            report = Report.objects.get(id=id)
        except Report.DoesNotExist:
            return Response({'message': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

        report.status = Report.Status.DISMISSED
        report.reviewed_by = request.user
        report.resolution_note = request.data.get('resolution_note', 'Dismissed by administrator.')
        report.resolved_at = timezone.now()
        report.save()

        log_activity(
            user=request.user,
            action='REPORT_DISMISSED',
            entity_type='Report',
            entity_id=report.id
        )

        return Response({
            'message': 'Report dismissed.',
            'report': ReportSerializer(report).data
        }, status=status.HTTP_200_OK)
