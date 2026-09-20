from rest_framework import generics, permissions, pagination
from rest_framework.response import Response
from apps.common.models import ActivityLog
from rest_framework import serializers

class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ['id', 'action', 'entity_type', 'entity_id', 'metadata', 'created_at']

class ActivityPagination(pagination.PageNumberPagination):
    page_size = 20
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

class UserActivityListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ActivityLogSerializer
    pagination_class = ActivityPagination

    def get_queryset(self):
        user = self.request.user
        queryset = ActivityLog.objects.filter(user=user)

        action = self.request.query_params.get('action', '').strip()
        if action:
            queryset = queryset.filter(action__icontains=action)

        entity_type = self.request.query_params.get('entity_type', '').strip()
        if entity_type:
            queryset = queryset.filter(entity_type__icontains=entity_type)

        return queryset.order_by('-created_at')
