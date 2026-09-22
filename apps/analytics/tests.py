from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from decimal import Decimal

from apps.apartments.models import Apartment
from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.shares.models import FoodShare, ShareRequest

User = get_user_model()

class AnalyticsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment = Apartment.objects.create(name='Eco Horizon')

        self.resident = User.objects.create_user(
            email='resident@analytics.local',
            password='Password123!',
            full_name='Analytics Resident',
            apartment=self.apartment,
            role=User.Role.RESIDENT
        )

        self.food_item = FoodItem.objects.create(
            user=self.resident,
            name='Fresh Tomatoes',
            category='VEGETABLES',
            quantity=Decimal('3.00'),
            unit='kg',
            expiry_date=date.today() + timedelta(days=5)
        )

        ConsumptionRecord.objects.create(
            food_item=self.food_item,
            user=self.resident,
            quantity=Decimal('1.00'),
            unit='kg'
        )

        WasteRecord.objects.create(
            food_item=self.food_item,
            user=self.resident,
            quantity=Decimal('0.50'),
            unit='kg',
            reason=WasteRecord.Reason.SPOILED
        )

        self.food_share = FoodShare.objects.create(
            food_item=self.food_item,
            owner=self.resident,
            title='1.5kg Tomatoes',
            initial_quantity=Decimal('1.50'),
            quantity=Decimal('0.00'),
            unit='kg',
            status=FoodShare.Status.COMPLETED
        )

    def test_analytics_overview(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/analytics/overview/?period=30d')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('overview', res.data)
        self.assertIn('impact', res.data)
        self.assertEqual(res.data['overview']['items_added'], 1)
        self.assertEqual(res.data['overview']['consumed_count'], 1)
        self.assertEqual(res.data['overview']['wasted_count'], 1)

    def test_analytics_consumption_breakdown(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/analytics/consumption/?period=30d')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('by_category', res.data)
        self.assertIn('daily_trend', res.data)

    def test_analytics_waste_breakdown(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/analytics/waste/?period=30d')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('by_reason', res.data)
        self.assertIn('by_category', res.data)

    def test_analytics_sharing_metrics(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/analytics/sharing/?period=30d')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('total_shared_kg', res.data)

    def test_analytics_unauthenticated_denied(self):
        res = self.client.get('/api/analytics/overview/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
