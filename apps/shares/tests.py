from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from apps.apartments.models import Apartment
from apps.foods.models import FoodItem
from apps.shares.models import FoodShare, ShareRequest, SavedShare
from apps.notifications.models import Notification
from apps.common.models import ActivityLog

User = get_user_model()

class Phase4SharesTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment_a = Apartment.objects.create(name="Green Heights")
        self.apartment_b = Apartment.objects.create(name="Blue Palms")

        # User A (Owner in Apartment A)
        self.user_a = User.objects.create_user(
            email="usera@example.com",
            password="password123",
            full_name="User A",
            apartment=self.apartment_a,
            flat_number="101"
        )

        # User B (Requester in Apartment A)
        self.user_b = User.objects.create_user(
            email="userb@example.com",
            password="password123",
            full_name="User B",
            apartment=self.apartment_a,
            flat_number="102"
        )

        # User C (Resident in Apartment B - isolated)
        self.user_c = User.objects.create_user(
            email="userc@example.com",
            password="password123",
            full_name="User C",
            apartment=self.apartment_b,
            flat_number="201"
        )

        # Create FoodItem for User A
        self.food_item = FoodItem.objects.create(
            user=self.user_a,
            name="Organic Apples",
            category=FoodItem.Category.FRUITS,
            quantity=Decimal('10.00'),
            unit=FoodItem.Unit.KG,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=7),
            storage_location=FoodItem.StorageLocation.REFRIGERATOR,
            estimated_value=Decimal('20.00')
        )

    def test_01_create_food_share_success(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'food_item_id': self.food_item.id,
            'title': 'Surplus Organic Apples',
            'description': 'Fresh apples to give away',
            'quantity': '4.00',
            'unit': 'kg',
            'visibility': 'APARTMENT',
            'pickup_note': 'Ring bell 101'
        }
        res = self.client.post('/api/shares/create/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FoodShare.objects.count(), 1)

        share = FoodShare.objects.first()
        self.assertEqual(share.title, 'Surplus Organic Apples')
        self.assertEqual(share.quantity, Decimal('4.00'))
        self.assertEqual(share.owner, self.user_a)

        # Check ActivityLog & Notification
        self.assertTrue(ActivityLog.objects.filter(action='FOOD_SHARE_CREATED').exists())
        self.assertTrue(Notification.objects.filter(user=self.user_a, type=Notification.Type.SHARE_CREATED).exists())

    def test_02_create_food_share_exceeds_quantity_fails(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'food_item_id': self.food_item.id,
            'title': 'Too Much Apples',
            'quantity': '15.00', # Food item only has 10.00
            'unit': 'kg'
        }
        res = self.client.post('/api/shares/create/', payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_03_apartment_isolation_in_community_feed(self):
        # Create share for User A in Apartment A
        share = FoodShare.objects.create(
            food_item=self.food_item,
            owner=self.user_a,
            title="Apples Share",
            initial_quantity=Decimal('3.00'),
            quantity=Decimal('3.00'),
            unit="kg",
            visibility=FoodShare.Visibility.APARTMENT
        )

        # User B (same apartment) should see share
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get('/api/shares/')
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        self.assertEqual(res_b.data['count'], 1)

        # User C (different apartment) should NOT see share
        self.client.force_authenticate(user=self.user_c)
        res_c = self.client.get('/api/shares/')
        self.assertEqual(res_c.status_code, status.HTTP_200_OK)
        self.assertEqual(res_c.data['count'], 0)

    def test_04_share_request_workflow_complete(self):
        # Step 1: User A creates share
        share = FoodShare.objects.create(
            food_item=self.food_item,
            owner=self.user_a,
            title="Fresh Oranges",
            initial_quantity=Decimal('5.00'),
            quantity=Decimal('5.00'),
            unit="kg",
            visibility=FoodShare.Visibility.APARTMENT,
            pickup_note="Leave at door"
        )

        # Step 2: User B requests 2 kg
        self.client.force_authenticate(user=self.user_b)
        res_req = self.client.post(f'/api/shares/{share.id}/request/', {'quantity': '2.00', 'message': 'Can I have some?'})
        self.assertEqual(res_req.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ShareRequest.objects.count(), 1)
        req_obj = ShareRequest.objects.first()
        self.assertEqual(req_obj.status, ShareRequest.Status.PENDING)

        # Check notification sent to User A (owner)
        self.assertTrue(Notification.objects.filter(user=self.user_a, type=Notification.Type.SHARE_REQUEST_RECEIVED).exists())

        # Step 3: User A approves request
        self.client.force_authenticate(user=self.user_a)
        res_appr = self.client.post(f'/api/shares/requests/{req_obj.id}/approve/')
        self.assertEqual(res_appr.status_code, status.HTTP_200_OK)
        req_obj.refresh_from_db()
        self.assertEqual(req_obj.status, ShareRequest.Status.APPROVED)

        # Check notification sent to User B (requester)
        self.assertTrue(Notification.objects.filter(user=self.user_b, type=Notification.Type.SHARE_REQUEST_APPROVED).exists())

        # Step 4: User A completes handover
        res_comp = self.client.post(f'/api/shares/requests/{req_obj.id}/complete/')
        self.assertEqual(res_comp.status_code, status.HTTP_200_OK)

        req_obj.refresh_from_db()
        share.refresh_from_db()
        self.food_item.refresh_from_db()

        self.assertEqual(req_obj.status, ShareRequest.Status.COMPLETED)
        self.assertEqual(share.quantity, Decimal('3.00')) # 5 - 2 = 3
        self.assertEqual(self.food_item.quantity, Decimal('8.00')) # 10 - 2 = 8

        # Check activity logs
        self.assertTrue(ActivityLog.objects.filter(action='SHARE_COMPLETED').exists())

    def test_05_cancel_share_releases_quantity(self):
        share = FoodShare.objects.create(
            food_item=self.food_item,
            owner=self.user_a,
            title="Share To Cancel",
            initial_quantity=Decimal('4.00'),
            quantity=Decimal('4.00'),
            unit="kg"
        )

        self.client.force_authenticate(user=self.user_a)
        res = self.client.post(f'/api/shares/{share.id}/cancel/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        share.refresh_from_db()
        self.assertEqual(share.status, FoodShare.Status.CANCELLED)

    def test_06_toggle_save_share(self):
        share = FoodShare.objects.create(
            food_item=self.food_item,
            owner=self.user_a,
            title="Saved Share Test",
            initial_quantity=Decimal('2.00'),
            quantity=Decimal('2.00'),
            unit="kg"
        )

        self.client.force_authenticate(user=self.user_b)
        res_save = self.client.post(f'/api/shares/{share.id}/save/')
        self.assertEqual(res_save.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SavedShare.objects.filter(user=self.user_b, share=share).exists())

        res_unsave = self.client.post(f'/api/shares/{share.id}/save/')
        self.assertEqual(res_unsave.status_code, status.HTTP_200_OK)
        self.assertFalse(SavedShare.objects.filter(user=self.user_b, share=share).exists())
