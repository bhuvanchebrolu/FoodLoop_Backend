from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.apartments.models import Apartment
from apps.users.models import CustomUser, UserSettings
from apps.common.models import ActivityLog

class Phase1ExtensionBackendTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment = Apartment.objects.create(
            name="Green Heights",
            address="124 Eco Park Avenue"
        )
        self.resident = CustomUser.objects.create_user(
            email="resident@test.com",
            password="TestPassword123!",
            full_name="Test Resident",
            apartment=self.apartment,
            flat_number="A-201",
            role=CustomUser.Role.RESIDENT
        )
        self.admin = CustomUser.objects.create_superuser(
            email="admin@test.com",
            password="AdminPassword123!",
            full_name="Test Admin",
            apartment=self.apartment,
            flat_number="A-101",
            role=CustomUser.Role.ADMIN
        )

    # 1. Registration Tests
    def test_registration_success(self):
        data = {
            "full_name": "New Resident",
            "email": "new@test.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "apartment_id": self.apartment.id,
            "flat_number": "B-303"
        }
        response = self.client.post(reverse('auth-register'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], "new@test.com")
        self.assertEqual(response.data['user']['role'], "RESIDENT")
        
        # Verify UserSettings auto-created
        new_user = CustomUser.objects.get(email="new@test.com")
        self.assertTrue(UserSettings.objects.filter(user=new_user).exists())
        
        # Verify ActivityLog recorded
        self.assertTrue(ActivityLog.objects.filter(user=new_user, action='USER_REGISTERED').exists())

    def test_registration_duplicate_email(self):
        data = {
            "full_name": "Duplicate User",
            "email": "resident@test.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        response = self.client.post(reverse('auth-register'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('errors', response.data)

    def test_registration_invalid_input(self):
        data = {
            "full_name": "",
            "email": "invalidemail",
            "password": "123",
            "confirm_password": "456"
        }
        response = self.client.post(reverse('auth-register'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # 2. Authentication Tests
    def test_login_success(self):
        data = {
            "email": "resident@test.com",
            "password": "TestPassword123!"
        }
        response = self.client.post(reverse('auth-login'), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertTrue(ActivityLog.objects.filter(user=self.resident, action='USER_LOGGED_IN').exists())

    def test_login_invalid_password(self):
        data = {
            "email": "resident@test.com",
            "password": "WrongPassword!"
        }
        response = self.client.post(reverse('auth-login'), data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_without_auth(self):
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # 3. Profile Tests
    def test_profile_access_authenticated(self):
        self.client.force_authenticate(user=self.resident)
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.resident.email)
        self.assertEqual(response.data['role'], 'RESIDENT')
        self.assertEqual(response.data['apartment']['name'], 'Green Heights')

    def test_profile_update_success(self):
        self.client.force_authenticate(user=self.resident)
        data = {
            "full_name": "Updated Resident Name",
            "flat_number": "A-999"
        }
        response = self.client.patch(reverse('auth-profile'), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resident.refresh_from_db()
        self.assertEqual(self.resident.full_name, "Updated Resident Name")
        self.assertEqual(self.resident.flat_number, "A-999")
        self.assertTrue(ActivityLog.objects.filter(user=self.resident, action='PROFILE_UPDATED').exists())

    def test_profile_role_tampering_prevention(self):
        self.client.force_authenticate(user=self.resident)
        data = {
            "role": "ADMIN"
        }
        response = self.client.patch(reverse('auth-profile'), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resident.refresh_from_db()
        self.assertEqual(self.resident.role, "RESIDENT") # Role should remain unchanged

    # 4. Settings Tests
    def test_get_user_settings(self):
        self.client.force_authenticate(user=self.resident)
        response = self.client.get(reverse('users-settings'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile_visibility'], 'COMMUNITY')
        self.assertTrue(response.data['expiry_notifications'])

    def test_update_user_settings(self):
        self.client.force_authenticate(user=self.resident)
        data = {
            "profile_visibility": "PRIVATE",
            "expiry_notifications": False
        }
        response = self.client.patch(reverse('users-settings'), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings_obj = UserSettings.objects.get(user=self.resident)
        self.assertEqual(settings_obj.profile_visibility, "PRIVATE")
        self.assertFalse(settings_obj.expiry_notifications)
        self.assertTrue(ActivityLog.objects.filter(user=self.resident, action='SETTINGS_UPDATED').exists())

    def test_unauthorized_settings_access(self):
        response = self.client.get(reverse('users-settings'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
