from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
from apps.users.models import CustomUser
from apps.apartments.models import Apartment
from apps.foods.models import FoodItem

class FoodItemAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment = Apartment.objects.create(name="Green Heights", address="124 Eco Park")
        
        # User 1
        self.user1 = CustomUser.objects.create_user(
            email="user1@foodloop.com",
            password="Password123!",
            full_name="User One",
            apartment=self.apartment,
            flat_number="101"
        )
        
        # User 2
        self.user2 = CustomUser.objects.create_user(
            email="user2@foodloop.com",
            password="Password123!",
            full_name="User Two",
            apartment=self.apartment,
            flat_number="102"
        )

        today = date.today()
        # Seed 3 items for User 1
        self.food1_available = FoodItem.objects.create(
            user=self.user1,
            name="Fresh Apples",
            category=FoodItem.Category.FRUITS,
            quantity=Decimal("5.00"),
            unit=FoodItem.Unit.PIECES,
            purchase_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=10), # AVAILABLE
            storage_location=FoodItem.StorageLocation.PANTRY,
            estimated_value=Decimal("4.00")
        )

        self.food1_expiring = FoodItem.objects.create(
            user=self.user1,
            name="Organic Milk",
            category=FoodItem.Category.DAIRY,
            quantity=Decimal("1.00"),
            unit=FoodItem.Unit.LITRES,
            purchase_date=today - timedelta(days=1),
            expiry_date=today + timedelta(days=2), # EXPIRING_SOON
            storage_location=FoodItem.StorageLocation.REFRIGERATOR,
            estimated_value=Decimal("3.50")
        )

        self.food1_expired = FoodItem.objects.create(
            user=self.user1,
            name="Old Bread",
            category=FoodItem.Category.BAKERY,
            quantity=Decimal("1.00"),
            unit=FoodItem.Unit.PACKET,
            purchase_date=today - timedelta(days=7),
            expiry_date=today - timedelta(days=1), # EXPIRED
            storage_location=FoodItem.StorageLocation.PANTRY,
            estimated_value=Decimal("2.50")
        )

        # Seed 1 item for User 2
        self.food2_private = FoodItem.objects.create(
            user=self.user2,
            name="Secret Chocolate",
            category=FoodItem.Category.SNACKS,
            quantity=Decimal("2.00"),
            unit=FoodItem.Unit.BOX,
            purchase_date=today,
            expiry_date=today + timedelta(days=30),
            storage_location=FoodItem.StorageLocation.PANTRY,
            estimated_value=Decimal("10.00")
        )

    # 1. Create Tests
    def test_create_food_item_success(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            "name": "Orange Juice",
            "category": "BEVERAGES",
            "quantity": 2,
            "unit": "litres",
            "purchase_date": str(date.today()),
            "expiry_date": str(date.today() + timedelta(days=7)),
            "storage_location": "REFRIGERATOR",
            "estimated_value": 5.50
        }
        response = self.client.post(reverse('food-list-create'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Orange Juice")
        self.assertEqual(response.data['status'], "AVAILABLE")

    def test_create_food_item_invalid_quantity(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            "name": "Invalid Quantity Item",
            "category": "FRUITS",
            "quantity": -1,
            "unit": "kg",
            "purchase_date": str(date.today()),
            "expiry_date": str(date.today() + timedelta(days=5))
        }
        response = self.client.post(reverse('food-list-create'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)

    def test_create_food_item_expiry_before_purchase(self):
        self.client.force_authenticate(user=self.user1)
        data = {
            "name": "Time Traveler Food",
            "category": "DAIRY",
            "quantity": 1,
            "unit": "packet",
            "purchase_date": str(date.today()),
            "expiry_date": str(date.today() - timedelta(days=2))
        }
        response = self.client.post(reverse('food-list-create'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expiry_date', response.data)

    # 2. Read & User Isolation Tests
    def test_user_sees_only_own_food_items(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(reverse('food-list-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        item_names = [item['name'] for item in response.data['results']]
        self.assertIn("Fresh Apples", item_names)
        self.assertNotIn("Secret Chocolate", item_names)

    def test_user_cannot_access_another_users_food_detail(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(reverse('food-detail', kwargs={'id': self.food2_private.id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 3. Update & User Isolation
    def test_update_own_food_item(self):
        self.client.force_authenticate(user=self.user1)
        data = {"name": "Fresh Gala Apples", "quantity": 10}
        response = self.client.patch(reverse('food-detail', kwargs={'id': self.food1_available.id}), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.food1_available.refresh_from_db()
        self.assertEqual(self.food1_available.name, "Fresh Gala Apples")

    def test_user_cannot_update_another_users_food_item(self):
        self.client.force_authenticate(user=self.user1)
        data = {"name": "Hacked Chocolate"}
        response = self.client.patch(reverse('food-detail', kwargs={'id': self.food2_private.id}), data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 4. Delete & User Isolation
    def test_delete_own_food_item(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(reverse('food-detail', kwargs={'id': self.food1_expired.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(FoodItem.objects.filter(id=self.food1_expired.id).exists())

    def test_user_cannot_delete_another_users_food_item(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(reverse('food-detail', kwargs={'id': self.food2_private.id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(FoodItem.objects.filter(id=self.food2_private.id).exists())

    # 5. Search, Filter, Sort & Status Calculation
    def test_search_filtering_and_sorting(self):
        self.client.force_authenticate(user=self.user1)
        
        # Search by name
        res_search = self.client.get(reverse('food-list-create') + '?search=Apples')
        self.assertEqual(res_search.data['count'], 1)

        # Filter by category
        res_cat = self.client.get(reverse('food-list-create') + '?category=DAIRY')
        self.assertEqual(res_cat.data['count'], 1)
        self.assertEqual(res_cat.data['results'][0]['name'], "Organic Milk")

        # Filter by status
        res_status = self.client.get(reverse('food-list-create') + '?status=EXPIRING_SOON')
        self.assertEqual(res_status.data['count'], 1)

    # 6. Dashboard Aggregation
    def test_dashboard_aggregated_metrics(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(reverse('food-dashboard'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_food_items'], 3)
        self.assertEqual(response.data['available_items'], 1)
        self.assertEqual(response.data['expiring_soon'], 1)
        self.assertEqual(response.data['expired_items'], 1)
        self.assertEqual(Decimal(str(response.data['total_estimated_value'])), Decimal("10.00"))
