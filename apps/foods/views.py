from rest_framework import status, permissions, generics, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.db.models.functions import Coalesce
from decimal import Decimal
from .models import FoodItem
from .serializers import FoodItemSerializer, FoodDashboardSerializer
from apps.common.permissions import IsOwnerOrAdmin

class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 10
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


class FoodItemListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FoodItemSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Update dynamic statuses based on current date before querying
        today_items = FoodItem.objects.filter(user=self.request.user)
        for item in today_items:
            new_status = item.compute_status()
            if new_status != item.status:
                FoodItem.objects.filter(id=item.id).update(status=new_status)

        queryset = FoodItem.objects.filter(user=self.request.user)

        # 1. Search Query (?search=milk)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(category__icontains=search) |
                Q(storage_location__icontains=search)
            )

        # 2. Category Filter (?category=DAIRY)
        category = self.request.query_params.get('category', '').strip()
        if category and category != 'ALL':
            queryset = queryset.filter(category=category.upper())

        # 3. Storage Location Filter (?storage=REFRIGERATOR)
        storage = self.request.query_params.get('storage', '').strip()
        if storage and storage != 'ALL':
            queryset = queryset.filter(storage_location=storage.upper())

        # 4. Status Filter (?status=EXPIRING_SOON)
        status_param = self.request.query_params.get('status', '').strip()
        if status_param and status_param != 'ALL':
            queryset = queryset.filter(status=status_param.upper())

        # 5. Sorting (?ordering=expiry_date)
        ordering = self.request.query_params.get('ordering', 'expiry_date').strip()
        valid_orderings = [
            'expiry_date', '-expiry_date',
            'purchase_date', '-purchase_date',
            'name', '-name',
            'created_at', '-created_at',
            'quantity', '-quantity'
        ]
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('expiry_date', 'name')

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FoodItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = FoodItemSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return FoodItem.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'Food item deleted successfully.'
        }, status=status.HTTP_200_OK)


class FoodDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Update dynamic statuses for accurate metrics
        user_items = FoodItem.objects.filter(user=request.user)
        for item in user_items:
            new_status = item.compute_status()
            if new_status != item.status:
                FoodItem.objects.filter(id=item.id).update(status=new_status)

        total_food_items = user_items.count()
        available_items = user_items.filter(status=FoodItem.Status.AVAILABLE).count()
        expiring_soon = user_items.filter(status=FoodItem.Status.EXPIRING_SOON).count()
        expired_items = user_items.filter(status=FoodItem.Status.EXPIRED).count()

        val_agg = user_items.aggregate(total_val=Sum('estimated_value'))
        total_estimated_value = val_agg['total_val'] or Decimal('0.00')

        cat_counts_qs = user_items.values('category').annotate(count=Count('id'))
        category_counts = {item['category']: item['count'] for item in cat_counts_qs}

        storage_counts_qs = user_items.values('storage_location').annotate(count=Count('id'))
        storage_counts = {item['storage_location']: item['count'] for item in storage_counts_qs}

        data = {
            'total_food_items': total_food_items,
            'available_items': available_items,
            'expiring_soon': expiring_soon,
            'expired_items': expired_items,
            'total_estimated_value': total_estimated_value,
            'category_counts': category_counts,
            'storage_counts': storage_counts,
        }

        serializer = FoodDashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)
