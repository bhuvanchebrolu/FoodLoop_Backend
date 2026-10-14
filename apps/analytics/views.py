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

        from django.db import connection

        # Heavy SQL query using WITH clause (CTE), Subqueries, Aggregate Functions, and COALESCE
        sql_overview = """
        WITH user_foods AS (
            SELECT id FROM foods_fooditem WHERE user_id = %s AND created_at >= %s
        ),
        user_consumed AS (
            SELECT id, quantity FROM foods_consumptionrecord WHERE user_id = %s AND consumed_at >= %s
        ),
        user_wasted AS (
            SELECT id, quantity FROM foods_wasterecord WHERE user_id = %s AND wasted_at >= %s
        ),
        user_shares AS (
            SELECT id, status, initial_quantity FROM shares_foodshare WHERE owner_id = %s AND created_at >= %s
        ),
        user_requests AS (
            SELECT id, status FROM shares_sharerequest WHERE requester_id = %s AND created_at >= %s
        )
        SELECT 
            (SELECT COUNT(*) FROM user_foods) AS items_added,
            (SELECT COUNT(*) FROM user_consumed) AS consumed_count,
            (SELECT COALESCE(SUM(quantity), 0.0) FROM user_consumed) AS consumed_total_kg,
            (SELECT COUNT(*) FROM user_wasted) AS wasted_count,
            (SELECT COALESCE(SUM(quantity), 0.0) FROM user_wasted) AS wasted_total_kg,
            (SELECT COUNT(*) FROM user_shares) AS shares_created,
            (SELECT COUNT(*) FROM user_shares WHERE status = 'COMPLETED') AS shares_completed,
            (SELECT COALESCE(SUM(initial_quantity), 0.0) FROM user_shares WHERE status = 'COMPLETED') AS food_shared_kg,
            (SELECT COUNT(*) FROM user_requests) AS requests_made,
            (SELECT COUNT(*) FROM user_requests WHERE status = 'COMPLETED') AS requests_completed;
        """

        params = [
            user.id, start_date,
            user.id, start_date,
            user.id, start_date,
            user.id, start_date,
            user.id, start_date
        ]

        with connection.cursor() as cursor:
            cursor.execute(sql_overview, params)
            row = cursor.fetchone()
            (
                items_added, consumed_count, consumed_total_kg,
                wasted_count, wasted_total_kg, shares_created_count,
                shares_completed_count, food_shared_kg, requests_made_count,
                requests_completed_count
            ) = row

        consumed_total_kg = float(consumed_total_kg or 0.0)
        wasted_total_kg = float(wasted_total_kg or 0.0)
        food_shared_kg = float(food_shared_kg or 0.0)

        # 5. Financial & Eco Impact calculations
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

        # Group by category with JOIN to FoodItem table, GROUP BY & ORDER BY
        qs = ConsumptionRecord.objects.filter(user=user, consumed_at__gte=start_date).select_related('food_item')

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

        # Group by daily trend with TruncDate aggregation
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

        qs = WasteRecord.objects.filter(user=user, wasted_at__gte=start_date).select_related('food_item')

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

        # Group by category with Multi-table JOIN
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

        # Daily trend with TruncDate
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


class AnalyticsLeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db import connection

        # Heavy SQL Query featuring Window Functions (DENSE_RANK OVER PARTITION BY & OVER ORDER BY)
        sql_leaderboard = """
        WITH user_stats AS (
            SELECT 
                u.id AS user_id,
                u.full_name,
                u.apartment_id,
                COALESCE(SUM(s.initial_quantity), 0.0) AS total_shared_kg,
                COUNT(s.id) AS completed_shares_count
            FROM users_customuser u
            LEFT JOIN shares_foodshare s ON u.id = s.owner_id AND s.status = 'COMPLETED'
            GROUP BY u.id, u.full_name, u.apartment_id
        ),
        ranked_users AS (
            SELECT 
                user_id,
                full_name,
                apartment_id,
                total_shared_kg,
                completed_shares_count,
                DENSE_RANK() OVER (ORDER BY total_shared_kg DESC) AS global_rank,
                DENSE_RANK() OVER (PARTITION BY apartment_id ORDER BY total_shared_kg DESC) AS apartment_rank
            FROM user_stats
        )
        SELECT user_id, full_name, apartment_id, total_shared_kg, completed_shares_count, global_rank, apartment_rank
        FROM ranked_users
        ORDER BY global_rank ASC
        LIMIT 20;
        """

        leaderboard = []
        with connection.cursor() as cursor:
            cursor.execute(sql_leaderboard)
            rows = cursor.fetchall()
            for r in rows:
                leaderboard.append({
                    'user_id': r[0],
                    'full_name': r[1],
                    'apartment_id': r[2],
                    'total_shared_kg': float(r[3]),
                    'completed_shares_count': r[4],
                    'global_rank': r[5],
                    'apartment_rank': r[6]
                })

        return Response({
            'leaderboard': leaderboard
        }, status=status.HTTP_200_OK)


class AnalyticsTrendsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db import connection

        # Heavy SQL Query with Window Functions: Rolling 7-day Moving Average, LAG(), and Cumulative SUM
        sql_window_trends = """
        WITH daily_consumption AS (
            SELECT 
                DATE(consumed_at) AS log_date,
                SUM(quantity) AS daily_qty
            FROM foods_consumptionrecord
            WHERE user_id = %s
            GROUP BY DATE(consumed_at)
        )
        SELECT 
            log_date,
            daily_qty,
            AVG(daily_qty) OVER (
                ORDER BY log_date 
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) AS rolling_7day_avg,
            SUM(daily_qty) OVER (
                ORDER BY log_date
            ) AS cumulative_qty,
            LAG(daily_qty, 1) OVER (ORDER BY log_date) AS prev_day_qty
        FROM daily_consumption
        ORDER BY log_date ASC;
        """

        trends = []
        with connection.cursor() as cursor:
            cursor.execute(sql_window_trends, [request.user.id])
            rows = cursor.fetchall()
            for r in rows:
                trends.append({
                    'date': r[0].isoformat() if r[0] else None,
                    'daily_quantity_kg': round(float(r[1] or 0), 2),
                    'rolling_7day_avg_kg': round(float(r[2] or 0), 2),
                    'cumulative_qty_kg': round(float(r[3] or 0), 2),
                    'prev_day_qty_kg': round(float(r[4] or 0), 2) if r[4] is not None else None
                })

        return Response({'trends': trends}, status=status.HTTP_200_OK)


class AnalyticsBadgesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db import connection

        # Refresh Materialized View first
        with connection.cursor() as cursor:
            cursor.execute("REFRESH MATERIALIZED VIEW mview_user_eco_badges;")

        sql_badges = """
        SELECT user_id, full_name, total_shared_kg, completed_shares_count, percentile, quartile
        FROM mview_user_eco_badges
        WHERE user_id = %s;
        """

        with connection.cursor() as cursor:
            cursor.execute(sql_badges, [request.user.id])
            row = cursor.fetchone()
            if not row:
                return Response({
                    'user_id': request.user.id,
                    'full_name': request.user.full_name,
                    'badge': 'Eco Starter 🌱',
                    'percentile_rank_percent': 0.0,
                    'quartile': 4
                }, status=status.HTTP_200_OK)

            user_id, full_name, total_shared_kg, completed_shares_count, percentile, quartile = row

        percentile_pct = round(float(percentile or 0.0) * 100, 1)

        badge_name = "Eco Starter 🌱"
        if percentile_pct >= 90:
            badge_name = "Zero-Waste Master 👑"
        elif percentile_pct >= 75:
            badge_name = "Community Champion 🏆"
        elif percentile_pct >= 50:
            badge_name = "Food Saver Veteran ⭐"

        return Response({
            'user_id': user_id,
            'full_name': full_name,
            'total_shared_kg': float(total_shared_kg or 0.0),
            'completed_shares_count': completed_shares_count,
            'percentile_rank_percent': percentile_pct,
            'quartile': quartile,
            'badge': badge_name
        }, status=status.HTTP_200_OK)

