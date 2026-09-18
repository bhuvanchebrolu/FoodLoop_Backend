from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
from apps.users.models import CustomUser, UserSettings
from apps.apartments.models import Apartment
from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.notifications.models import Notification
from apps.notifications.services import ExpiryEngineService

class Phase3BackendTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment = Apartment.objects.create(name="Green Heights", address="124 Eco Park")
        
        self.user1 = CustomUser.objects.create_user(
            email="user1@foodloop.com",
            password="Password123!",
            full_name="User One",
            apartment=self.apartment,
            flat_number="101"
        )
        
        self.user2 = CustomUser.objects.create_user(
            email="user2@foodloop.com",
            password="Password123!",
            full_name="User Two",
            apartment=self.apartment,
            flat_number="102"
        )

        today = date.today()

        # User 1 Food items
        self.milk = FoodItem.objects.create(
            user=self.user1,
            name="Whole Milk",
            category=FoodItem.Category.DAIRY,
            quantity=Decimal("2.00"),
            unit=FoodItem.Unit.LITRES,
            purchase_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=1), # EXPIRING_SOON (Urgent)
            storage_location=FoodItem.StorageLocation.REFRIGERATOR,
            estimated_value=Decimal("5.00")
        )

        self.apples = FoodItem.objects.create(
            user=self.user1,
            name="Apples",
            category=FoodItem.Category.FRUITS,
            quantity=Decimal("5.00"),
            unit=FoodItem.Unit.PIECES,
            purchase_date=today - timedelta(days=1),
            expiry_date=today + timedelta(days=10), # AVAILABLE (Good)
            storage_location=FoodItem.StorageLocation.PANTRY,
            estimated_value=Decimal("3.00")
        )

        self.bread = FoodItem.objects.create(
            user=self.user1,
            name="Stale Bread",
            category=FoodItem.Category.BAKERY,
            quantity=Decimal("1.00"),
            unit=FoodItem.Unit.PACKET,
            purchase_date=today - timedelta(days=6),
            expiry_date=today - timedelta(days=1), # EXPIRED
            storage_location=FoodItem.StorageLocation.PANTRY,
            estimated_value=Decimal("2.50")
        )

        # User 2 Food item
        self.user2_food = FoodItem.objects.create(
            user=self.user2,
            name="User2 Cheese",
            category=FoodItem.Category.DAIRY,
            quantity=Decimal("1.00"),
            unit=FoodItem.Unit.PACKET,
            purchase_date=today,
            expiry_date=today + timedelta(days=5),
            storage_location=FoodItem.StorageLocation.REFRIGERATOR,
            estimated_value=Decimal("4.00")
        )

    # 1. Consumption Tests
    def test_partial_consumption_success(self):
        self.client.force_authenticate(user=self.user1)
        data = {"quantity": 0.50}
        url = reverse('food-consume', kwargs={'id': self.milk.id})
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.quantity, Decimal("1.50"))
        self.assertTrue(ConsumptionRecord.objects.filter(food_item=self.milk, quantity=Decimal("0.50")).exists())

    def test_full_consumption_updates_status_to_consumed(self):
        self.client.force_authenticate(user=self.user1)
        data = {"quantity": 2.00}
        url = reverse('food-consume', kwargs={'id': self.milk.id})
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.quantity, Decimal("0.00"))
        self.assertEqual(self.milk.status, FoodItem.Status.CONSUMED)

    def test_over_consumption_rejected(self):
        self.client.force_authenticate(user=self.user1)
        data = {"quantity": 5.00}
        url = reverse('food-consume', kwargs={'id': self.milk.id})
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.quantity, Decimal("2.00")) # Unchanged

    def test_unauthorized_consumption_rejected(self):
        self.client.force_authenticate(user=self.user1)
        data = {"quantity": 0.50}
        url = reverse('food-consume', kwargs={'id': self.user2_food.id})
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 2. Waste Tests
    def test_waste_recording_success(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            "quantity": 1.00,
            "reason": "SPOILED",
            "description": "Milk went sour"
        }
        url = reverse('food-waste', kwargs={'id': self.milk.id})
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.quantity, Decimal("1.00"))
        self.assertTrue(WasteRecord.objects.filter(food_item=self.milk, reason="SPOILED").exists())

    # 3. Expiry Engine & Notification Tests
    def test_expiry_engine_and_idempotency(self):
        # Run engine for user1
        created_first = ExpiryEngineService.check_and_generate_expiry_notifications(self.user1)
        self.assertGreater(created_first, 0)
        
        # Run engine second time immediately -> idempotency should prevent duplicates
        created_second = ExpiryEngineService.check_and_generate_expiry_notifications(self.user1)
        self.assertEqual(created_second, 0)

    def test_expiry_notifications_disabled_preference(self):
        # Disable expiry notifications for user1
        settings_obj = UserSettings.objects.get(user=self.user1)
        settings_obj.expiry_notifications = False
        settings_obj.save()

        created = ExpiryEngineService.check_and_generate_expiry_notifications(self.user1)
        self.assertEqual(created, 0)

    def test_notification_list_and_mark_read(self):
        ExpiryEngineService.check_and_generate_expiry_notifications(self.user1)
        self.client.force_authenticate(user=self.user1)

        # List notifications
        res_list = self.client.get(reverse('notification-list'))
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertGreater(res_list.data['unread_count'], 0)

        notif_id = res_list.data['results'][0]['id']

        # Mark single as read
        res_read = self.client.patch(reverse('notification-mark-read', kwargs={'id': notif_id}))
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)

        # Mark all as read
        res_all = self.client.post(reverse('notification-mark-all-read'))
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.filter(user=self.user1, is_read=False).count(), 0)

    # 4. Alerts APIs Tests
    def test_alerts_summary_and_filtering(self):
        self.client.force_authenticate(user=self.user1)

        # Summary endpoint
        res_summary = self.client.get(reverse('alert-summary'))
        self.assertEqual(res_summary.status_code, status.HTTP_200_OK)
        self.assertEqual(res_summary.data['total_alerts'], 3)
        self.assertEqual(res_summary.data['urgent_count'], 1) # milk
        self.assertEqual(res_summary.data['expired_count'], 1) # bread

        # Filter by priority
        res_urgent = self.client.get(reverse('alert-list') + '?priority=URGENT')
        self.assertEqual(res_urgent.status_code, status.HTTP_200_OK)
        self.assertEqual(res_urgent.data['count'], 1)
        self.assertEqual(res_urgent.data['results'][0]['name'], "Whole Milk")
