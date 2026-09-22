from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.shares.models import FoodShare, ShareRequest

def get_start_date_for_period(period_param):
    today = date.today()
    period = str(period_param).lower().strip()
    if period == '7d':
        return today - timedelta(days=7)
    elif period == '3m':
        return today - timedelta(days=90)
    elif period == '6m':
        return today - timedelta(days=180)
    elif period == '1y':
        return today - timedelta(days=365)
    else: # Default 30d
        return today - timedelta(days=30)

class AnalyticsOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.query_params.get('period', '30d')
        start_date = get_start_date_for_period(period)

        # 1. Total Food Added in timeframe
        items_added = FoodItem.objects.filter(user=user, created_at__date__gte=start_date).count()

        # 2. Consumption metrics
        consumed_qs = ConsumptionRecord.objects.filter(user=user, consumed_at__gte=start_date)
        consumed_count = consumed_qs.count()
        consumed_total_kg = float(consumed_qs.aggregate(total=Sum('quantity'))['total'] or 0.0)

        # 3. Waste metrics
        wasted_qs = WasteRecord.objects.filter(user=user, wasted_at__gte=start_date)
        wasted_count = wasted_qs.count()
        wasted_total_kg = float(wasted_qs.aggregate(total=Sum('quantity'))['total'] or 0.0)

        # 4. Sharing metrics
        shares_created_qs = FoodShare.objects.filter(owner=user, created_at__date__gte=start_date)
        shares_created_count = shares_created_qs.count()

        shares_completed_qs = FoodShare.objects.filter(owner=user, status=FoodShare.Status.COMPLETED, updated_at__date__gte=start_date)
        shares_completed_count = shares_completed_qs.count()
        food_shared_kg = float(shares_completed_qs.aggregate(total=Sum('initial_quantity'))['total'] or 0.0)

        requests_made_count = ShareRequest.objects.filter(requester=user, created_at__date__gte=start_date).count()
        requests_completed_count = ShareRequest.objects.filter(requester=user, status=ShareRequest.Status.COMPLETED, updated_at__date__gte=start_date).count()

        # 5. Financial & Eco Impact
        food_saved_kg = round(consumed_total_kg + food_shared_kg, 2)
        diverted_waste_kg = round(food_shared_kg + (consumed_total_kg * 0.8), 2)
        estimated_money_saved_inr = round(food_saved_kg * 150.0, 2)

        sharing_efficiency = round((shares_completed_count / shares_created_count * 100.0), 1) if shares_created_count > 0 else 0.0

        return Response({
            'period': period,
            'start_date': start_date.isoformat(),
            'overview': {
                'items_added': items_added,
                'consumed_count': consumed_count,
                'consumed_total_kg': round(consumed_total_kg, 2),
                'wasted_count': wasted_count,
                'wasted_total_kg': round(wasted_total_kg, 2),
                'shares_created': shares_created_count,
                'shares_completed': shares_completed_count,
                'requests_made': requests_made_count,
                'requests_completed': requests_completed_count,
            },
            'impact': {
                'food_saved_kg': food_saved_kg,
                'food_shared_kg': round(food_shared_kg, 2),
                'diverted_waste_kg': diverted_waste_kg,
                'estimated_money_saved_inr': estimated_money_saved_inr,
                'sharing_efficiency_percent': sharing_efficiency,
            }
        }, status=status.HTTP_200_OK)


class AnalyticsConsumptionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.query_params.get('period', '30d')
        start_date = get_start_date_for_period(period)

        qs = ConsumptionRecord.objects.filter(user=user, consumed_at__gte=start_date)

        # Group by category
        by_category_qs = qs.values('food_item__category').annotate(
            total_qty=Sum('quantity'),
            record_count=Count('id')
        ).order_by('-total_qty')

        by_category = [
          {
              'category': item['food_item__category'] or 'OTHER',
              'quantity': round(float(item['total_qty']), 2),
              'count': item['record_count']
          }
          for item in by_category_qs
        ]

        # Group by daily trend
        daily_trend_qs = qs.annotate(day=TruncDate('consumed_at')).values('day').annotate(
            quantity=Sum('quantity'),
            count=Count('id')
        ).order_by('day')

        daily_trend = [
            {
                'date': item['day'].isoformat() if item['day'] else '',
                'quantity': round(float(item['quantity']), 2),
                'count': item['count']
            }
            for item in daily_trend_qs
        ]

        return Response({
            'period': period,
            'by_category': by_category,
            'daily_trend': daily_trend
        }, status=status.HTTP_200_OK)


class AnalyticsWasteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.query_params.get('period', '30d')
        start_date = get_start_date_for_period(period)

        qs = WasteRecord.objects.filter(user=user, wasted_at__gte=start_date)

        # Group by waste reason
        by_reason_qs = qs.values('reason').annotate(
            total_qty=Sum('quantity'),
            record_count=Count('id')
        ).order_by('-total_qty')

        by_reason = [
            {
                'reason': item['reason'],
                'quantity': round(float(item['total_qty']), 2),
                'count': item['record_count']
            }
            for item in by_reason_qs
        ]

        # Group by category
        by_category_qs = qs.values('food_item__category').annotate(
            total_qty=Sum('quantity'),
            record_count=Count('id')
        ).order_by('-total_qty')

        by_category = [
            {
                'category': item['food_item__category'] or 'OTHER',
                'quantity': round(float(item['total_qty']), 2),
                'count': item['record_count']
            }
            for item in by_category_qs
        ]

        # Daily trend
        daily_trend_qs = qs.annotate(day=TruncDate('wasted_at')).values('day').annotate(
            quantity=Sum('quantity'),
            count=Count('id')
        ).order_by('day')

        daily_trend = [
            {
                'date': item['day'].isoformat() if item['day'] else '',
                'quantity': round(float(item['quantity']), 2),
                'count': item['count']
            }
            for item in daily_trend_qs
        ]

        return Response({
            'period': period,
            'by_reason': by_reason,
            'by_category': by_category,
            'daily_trend': daily_trend
        }, status=status.HTTP_200_OK)


class AnalyticsSharingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.query_params.get('period', '30d')
        start_date = get_start_date_for_period(period)

        shares_created = FoodShare.objects.filter(owner=user, created_at__date__gte=start_date).count()
        shares_completed = FoodShare.objects.filter(owner=user, status=FoodShare.Status.COMPLETED, updated_at__date__gte=start_date).count()

        completed_shares_qs = FoodShare.objects.filter(owner=user, status=FoodShare.Status.COMPLETED, updated_at__date__gte=start_date)
        total_shared_kg = float(completed_shares_qs.aggregate(total=Sum('initial_quantity'))['total'] or 0.0)

        completed_requests_qs = ShareRequest.objects.filter(requester=user, status=ShareRequest.Status.COMPLETED, updated_at__date__gte=start_date)
        requests_completed_count = completed_requests_qs.count()
        total_received_kg = float(completed_requests_qs.aggregate(total=Sum('quantity'))['total'] or 0.0)

        return Response({
            'period': period,
            'shares_created': shares_created,
            'shares_completed': shares_completed,
            'total_shared_kg': round(total_shared_kg, 2),
            'requests_completed': requests_completed_count,
            'total_received_kg': round(total_received_kg, 2),
        }, status=status.HTTP_200_OK)


class AnalyticsImpactView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.query_params.get('period', '30d')
        start_date = get_start_date_for_period(period)

        consumed_kg = float(ConsumptionRecord.objects.filter(user=user, consumed_at__gte=start_date).aggregate(total=Sum('quantity'))['total'] or 0.0)
        wasted_kg = float(WasteRecord.objects.filter(user=user, wasted_at__gte=start_date).aggregate(total=Sum('quantity'))['total'] or 0.0)
        
        completed_shares_qs = FoodShare.objects.filter(owner=user, status=FoodShare.Status.COMPLETED, updated_at__date__gte=start_date)
        shared_kg = float(completed_shares_qs.aggregate(total=Sum('initial_quantity'))['total'] or 0.0)

        food_saved_kg = round(consumed_kg + shared_kg, 2)
        diverted_waste_kg = round(shared_kg + (consumed_kg * 0.8), 2)
        estimated_money_saved_inr = round(food_saved_kg * 150.0, 2)

        return Response({
            'period': period,
            'food_saved_kg': food_saved_kg,
            'food_shared_kg': round(shared_kg, 2),
            'food_wasted_kg': round(wasted_kg, 2),
            'diverted_waste_kg': diverted_waste_kg,
            'estimated_money_saved_inr': estimated_money_saved_inr,
        }, status=status.HTTP_200_OK)
