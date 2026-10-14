from rest_framework import status, permissions, generics, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction, models
from django.db.models import Q, Sum, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import FoodItem, ConsumptionRecord, WasteRecord
from .serializers import (
    FoodItemSerializer, 
    FoodDashboardSerializer,
    ConsumptionRecordSerializer,
    ConsumeActionSerializer,
    WasteRecordSerializer,
    WasteActionSerializer
)
from apps.common.permissions import IsOwnerOrAdmin
from apps.common.utils import log_activity

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
        # 1. Update statuses using a single DB-heavy atomic UPDATE with CASE WHEN subquery
        from django.db import connection
        with connection.cursor():
            FoodItem.objects.filter(user=self.request.user).exclude(status=FoodItem.Status.SHARED).update(
                status=models.Case(
                    models.When(quantity__lte=0, then=models.Value(FoodItem.Status.CONSUMED)),
                    models.When(expiry_date__lt=timezone.now().date(), then=models.Value(FoodItem.Status.EXPIRED)),
                    models.When(expiry_date__lte=timezone.now().date() + timedelta(days=3), then=models.Value(FoodItem.Status.EXPIRING_SOON)),
                    default=models.Value(FoodItem.Status.AVAILABLE),
                    output_field=models.CharField()
                )
            )

        # 2. Base Queryset using DB Subquery for User Isolation
        queryset = FoodItem.objects.filter(
            user_id__in=models.Subquery(
                FoodItem.objects.filter(user=self.request.user).values('user_id')[:1]
            )
        )

        # 3. Search Query (?search=milk)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(category__icontains=search) |
                Q(storage_location__icontains=search)
            )

        # 4. Category Filter (?category=DAIRY)
        category = self.request.query_params.get('category', '').strip()
        if category and category != 'ALL':
            queryset = queryset.filter(category=category.upper())

        # 5. Storage Location Filter (?storage=REFRIGERATOR)
        storage = self.request.query_params.get('storage', '').strip()
        if storage and storage != 'ALL':
            queryset = queryset.filter(storage_location=storage.upper())

        # 6. Status Filter (?status=EXPIRING_SOON)
        status_param = self.request.query_params.get('status', '').strip()
        if status_param and status_param != 'ALL':
            queryset = queryset.filter(status=status_param.upper())
        else:
            # Exclude consumed / zero-quantity items from default active pantry inventory view
            queryset = queryset.exclude(status=FoodItem.Status.CONSUMED).filter(quantity__gt=0)

        # 7. Sorting (?ordering=expiry_date) with ORDER BY
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
        from django.db import connection

        # Batch update statuses inside DB engine with raw SQL CASE expression
        FoodItem.objects.filter(user=request.user).exclude(status=FoodItem.Status.SHARED).update(
            status=models.Case(
                models.When(quantity__lte=0, then=models.Value(FoodItem.Status.CONSUMED)),
                models.When(expiry_date__lt=timezone.now().date(), then=models.Value(FoodItem.Status.EXPIRED)),
                models.When(expiry_date__lte=timezone.now().date() + timedelta(days=3), then=models.Value(FoodItem.Status.EXPIRING_SOON)),
                default=models.Value(FoodItem.Status.AVAILABLE),
                output_field=models.CharField()
            )
        )

        # Heavy SQL Query with CTE (WITH Clause), Subqueries, CASE WHEN, GROUP BY, ORDER BY & Aggregate Functions
        sql_dashboard = """
        WITH user_pantry AS (
            SELECT 
                id, 
                user_id, 
                category, 
                storage_location, 
                estimated_value,
                status,
                quantity
            FROM foods_fooditem
            WHERE user_id = %s
        ),
        active_pantry AS (
            SELECT * FROM user_pantry WHERE status != 'CONSUMED' AND quantity > 0
        )
        SELECT 
            (SELECT COUNT(*) FROM active_pantry) AS total_food_items,
            (SELECT COUNT(*) FROM active_pantry WHERE status = 'AVAILABLE') AS available_items,
            (SELECT COUNT(*) FROM active_pantry WHERE status = 'EXPIRING_SOON') AS expiring_soon,
            (SELECT COUNT(*) FROM active_pantry WHERE status = 'EXPIRED') AS expired_items,
            (SELECT COUNT(*) FROM user_pantry WHERE status = 'CONSUMED' OR quantity <= 0) AS consumed_items,
            (SELECT COALESCE(SUM(estimated_value), 0.00) FROM active_pantry) AS total_estimated_value;
        """

        with connection.cursor() as cursor:
            cursor.execute(sql_dashboard, [request.user.id])
            row = cursor.fetchone()
            total_food_items, available_items, expiring_soon, expired_items, consumed_items, total_estimated_value = row

        # Heavy DB GROUP BY + ORDER BY query for categories
        cat_counts_qs = FoodItem.objects.filter(user=request.user).exclude(status=FoodItem.Status.CONSUMED).filter(quantity__gt=0).values('category').annotate(count=Count('id')).order_by('-count')
        category_counts = {item['category']: item['count'] for item in cat_counts_qs}

        # Heavy DB GROUP BY + ORDER BY query for storage locations
        storage_counts_qs = FoodItem.objects.filter(user=request.user).exclude(status=FoodItem.Status.CONSUMED).filter(quantity__gt=0).values('storage_location').annotate(count=Count('id')).order_by('-count')
        storage_counts = {item['storage_location']: item['count'] for item in storage_counts_qs}

        data = {
            'total_food_items': total_food_items or 0,
            'available_items': available_items or 0,
            'expiring_soon': expiring_soon or 0,
            'expired_items': expired_items or 0,
            'consumed_items': consumed_items or 0,
            'total_estimated_value': Decimal(str(total_estimated_value or '0.00')),
            'category_counts': category_counts,
            'storage_counts': storage_counts,
        }

        serializer = FoodDashboardSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConsumeFoodView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        serializer = ConsumeActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid consumption data.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        requested_qty = serializer.validated_data['quantity']

        with transaction.atomic():
            try:
                food_item = FoodItem.objects.select_for_update().get(id=id, user=request.user)
            except FoodItem.DoesNotExist:
                return Response({'message': 'Food item not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

            if food_item.quantity < requested_qty:
                return Response({
                    'message': f'Cannot consume {requested_qty} {food_item.unit}. Only {food_item.quantity} {food_item.unit} remaining.'
                }, status=status.HTTP_400_BAD_REQUEST)

            record = ConsumptionRecord.objects.create(
                food_item=food_item,
                user=request.user,
                quantity=requested_qty,
                unit=food_item.unit
            )

            food_item.quantity -= requested_qty
            if food_item.quantity <= 0:
                food_item.quantity = Decimal('0.00')
                food_item.status = FoodItem.Status.CONSUMED

            food_item.save()

            log_activity(
                user=request.user,
                action='FOOD_CONSUMED',
                entity_type='FoodItem',
                entity_id=food_item.id,
                metadata={'consumed_quantity': str(requested_qty), 'remaining_quantity': str(food_item.quantity)}
            )

            return Response({
                'message': f'Recorded consumption of {requested_qty} {food_item.unit}.',
                'food_item': FoodItemSerializer(food_item, context={'request': request}).data,
                'consumption_record': ConsumptionRecordSerializer(record).data
            }, status=status.HTTP_200_OK)


class WasteFoodView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        serializer = WasteActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid waste data.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        requested_qty = serializer.validated_data['quantity']
        reason = serializer.validated_data['reason']
        description = serializer.validated_data.get('description', '')

        with transaction.atomic():
            try:
                food_item = FoodItem.objects.select_for_update().get(id=id, user=request.user)
            except FoodItem.DoesNotExist:
                return Response({'message': 'Food item not found or unauthorized.'}, status=status.HTTP_404_NOT_FOUND)

            if food_item.quantity < requested_qty:
                return Response({
                    'message': f'Cannot record waste of {requested_qty} {food_item.unit}. Only {food_item.quantity} {food_item.unit} remaining.'
                }, status=status.HTTP_400_BAD_REQUEST)

            prorated_value = Decimal('0.00')
            if food_item.quantity > 0 and food_item.estimated_value > 0:
                ratio = requested_qty / food_item.quantity
                prorated_value = (food_item.estimated_value * ratio).quantize(Decimal('0.01'))

            record = WasteRecord.objects.create(
                food_item=food_item,
                user=request.user,
                quantity=requested_qty,
                unit=food_item.unit,
                reason=reason,
                description=description,
                estimated_value=prorated_value
            )

            food_item.quantity -= requested_qty
            if food_item.quantity <= 0:
                food_item.quantity = Decimal('0.00')
                food_item.status = FoodItem.Status.EXPIRED

            food_item.save()

            log_activity(
                user=request.user,
                action='FOOD_WASTED',
                entity_type='FoodItem',
                entity_id=food_item.id,
                metadata={'wasted_quantity': str(requested_qty), 'reason': reason, 'remaining_quantity': str(food_item.quantity)}
            )

            return Response({
                'message': f'Recorded waste of {requested_qty} {food_item.unit}.',
                'food_item': FoodItemSerializer(food_item, context={'request': request}).data,
                'waste_record': WasteRecordSerializer(record).data
            }, status=status.HTTP_200_OK)


class ConsumptionHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConsumptionRecordSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = ConsumptionRecord.objects.filter(user=self.request.user)
        food_id = self.kwargs.get('id')
        if food_id:
            queryset = queryset.filter(food_item_id=food_id)
        return queryset


class WasteHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WasteRecordSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = WasteRecord.objects.filter(user=self.request.user)
        food_id = self.kwargs.get('id')
        if food_id:
            queryset = queryset.filter(food_item_id=food_id)
        return queryset


class FuzzyFoodSearchAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'results': []}, status=status.HTTP_200_OK)

        from django.db import connection

        # PostgreSQL pg_trgm fuzzy trigram similarity score query
        sql_trgm = """
        SELECT 
            id, name, category, storage_location, quantity, unit, expiry_date, status,
            similarity(name, %s) AS match_score
        FROM foods_fooditem
        WHERE user_id = %s AND (similarity(name, %s) > 0.1 OR name ILIKE %s)
        ORDER BY match_score DESC, name ASC
        LIMIT 20;
        """

        results = []
        with connection.cursor() as cursor:
            cursor.execute(sql_trgm, [query, request.user.id, query, f"%{query}%"])
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    'id': r[0],
                    'name': r[1],
                    'category': r[2],
                    'storage_location': r[3],
                    'quantity': str(r[4]),
                    'unit': r[5],
                    'expiry_date': r[6].isoformat() if r[6] else None,
                    'status': r[7],
                    'match_score': round(float(r[8]), 3)
                })

        return Response({'query': query, 'count': len(results), 'results': results}, status=status.HTTP_200_OK)
