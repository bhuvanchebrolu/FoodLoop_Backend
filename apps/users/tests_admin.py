from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.apartments.models import Apartment

User = get_user_model()

class AdminAndProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.apartment = Apartment.objects.create(name='Sunset Palms')

        self.resident = User.objects.create_user(
            email='resident@foodloop.local',
            password='Password123!',
            full_name='Resident Normal',
            apartment=self.apartment,
            role=User.Role.RESIDENT
        )

        self.admin1 = User.objects.create_superuser(
            email='admin1@foodloop.local',
            password='Password123!',
            full_name='Admin One'
        )

        self.admin2 = User.objects.create_user(
            email='admin2@foodloop.local',
            password='Password123!',
            full_name='Admin Two',
            role=User.Role.ADMIN
        )

    def test_resident_denied_admin_dashboard(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_dashboard_success(self):
        self.client.force_authenticate(user=self.admin1)
        res = self.client.get('/api/admin/dashboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('total_residents', res.data)
        self.assertIn('active_shares', res.data)

    def test_admin_deactivate_and_activate_user(self):
        self.client.force_authenticate(user=self.admin1)
        # Deactivate
        deact_res = self.client.post(f'/api/admin/users/{self.resident.id}/deactivate/')
        self.assertEqual(deact_res.status_code, status.HTTP_200_OK)
        self.resident.refresh_from_db()
        self.assertFalse(self.resident.is_active)

        # Activate
        act_res = self.client.post(f'/api/admin/users/{self.resident.id}/activate/')
        self.assertEqual(act_res.status_code, status.HTTP_200_OK)
        self.resident.refresh_from_db()
        self.assertTrue(self.resident.is_active)

    def test_prevent_sole_admin_demotion(self):
        # Delete admin2 so admin1 is the sole admin
        self.admin2.delete()

        self.client.force_authenticate(user=self.admin1)
        res = self.client.post(f'/api/admin/users/{self.admin1.id}/role/', {'role': 'RESIDENT'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_summary_endpoint(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/auth/profile-summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('stats', res.data)
        self.assertIn('impact', res.data)
        self.assertIn('food_saved_kg', res.data['impact'])

    def test_user_activity_endpoint(self):
        self.client.force_authenticate(user=self.resident)
        res = self.client.get('/api/activity/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
