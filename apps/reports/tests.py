from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.apartments.models import Apartment
from apps.foods.models import FoodItem
from apps.shares.models import FoodShare
from apps.reports.models import Report

User = get_user_model()

from datetime import date, timedelta

class ReportModerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment = Apartment.objects.create(name='Green Towers')
        
        self.resident = User.objects.create_user(
            email='resident@foodloop.local',
            password='Password123!',
            full_name='Resident User',
            apartment=self.apartment,
            role=User.Role.RESIDENT
        )

        self.resident2 = User.objects.create_user(
            email='resident2@foodloop.local',
            password='Password123!',
            full_name='Resident Two',
            apartment=self.apartment,
            role=User.Role.RESIDENT
        )

        self.admin_user = User.objects.create_superuser(
            email='admin@foodloop.local',
            password='Password123!',
            full_name='Admin User'
        )

        self.food_item = FoodItem.objects.create(
            user=self.resident,
            name='Fresh Milk',
            category='DAIRY',
            quantity=2.00,
            unit='litres',
            expiry_date=date.today() + timedelta(days=10)
        )

        self.food_share = FoodShare.objects.create(
            food_item=self.food_item,
            owner=self.resident,
            title='2L Fresh Milk',
            initial_quantity=2.00,
            quantity=2.00,
            unit='litres'
        )

    def test_resident_create_report(self):
        self.client.force_authenticate(user=self.resident2)
        url = '/api/reports/'
        payload = {
            'target_type': 'FOOD_SHARE',
            'target_id': str(self.food_share.id),
            'reason': 'INAPPROPRIATE_CONTENT',
            'description': 'Suspicious listing detail'
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Report.objects.filter(reporter=self.resident2).exists())

    def test_duplicate_pending_report_prevention(self):
        self.client.force_authenticate(user=self.resident2)
        url = '/api/reports/'
        payload = {
            'target_type': 'FOOD_SHARE',
            'target_id': str(self.food_share.id),
            'reason': 'SPAM',
            'description': 'Duplicate spam test'
        }
        res1 = self.client.post(url, payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(url, payload, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_review_and_resolve_report(self):
        report = Report.objects.create(
            reporter=self.resident2,
            target_type=Report.TargetType.FOOD_SHARE,
            target_id=str(self.food_share.id),
            reason=Report.Reason.INAPPROPRIATE_CONTENT,
            description='Bad image content'
        )

        # Non-admin access denied
        self.client.force_authenticate(user=self.resident)
        res_denied = self.client.post(f'/api/reports/admin/{report.id}/resolve/', {'action': 'CANCEL_SHARE'})
        self.assertEqual(res_denied.status_code, status.HTTP_403_FORBIDDEN)

        # Admin resolves report with share cancellation
        self.client.force_authenticate(user=self.admin_user)
        res_admin = self.client.post(f'/api/reports/admin/{report.id}/resolve/', {
            'action': 'CANCEL_SHARE',
            'resolution_note': 'Share removed due to terms violation.'
        }, format='json')

        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.RESOLVED)
        self.food_share.refresh_from_db()
        self.assertEqual(self.food_share.status, FoodShare.Status.CANCELLED)
