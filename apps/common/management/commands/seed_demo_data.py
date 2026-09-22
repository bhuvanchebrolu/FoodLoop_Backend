from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from apps.apartments.models import Apartment
from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.shares.models import FoodShare, ShareRequest
from apps.notifications.models import Notification
from apps.common.models import ActivityLog

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds realistic development demo data for FoodLoop Phase 1-6 testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding FoodLoop Demo Data..."))

        # 1. Ensure Apartments
        apt1, _ = Apartment.objects.get_or_create(
            name="Green Valley Eco Towers",
            defaults={'address': '104 Park Street, Green Zone'}
        )
        apt2, _ = Apartment.objects.get_or_create(
            name="Horizon Heights Residency",
            defaults={'address': '402 Skyline Boulevard'}
        )

        # 2. Ensure Admin & Resident Users
        admin_user, _ = User.objects.get_or_create(
            email="admin@gmail.com",
            defaults={
                'full_name': 'System Administrator',
                'apartment': apt1,
                'flat_number': 'ADMIN-1',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password("admin123")
        admin_user.role = User.Role.ADMIN
        admin_user.save()

        res1, _ = User.objects.get_or_create(
            email="resident1@gmail.com",
            defaults={
                'full_name': 'Aarav Sharma',
                'apartment': apt1,
                'flat_number': 'A-204',
                'role': User.Role.RESIDENT,
            }
        )
        res1.set_password("resident123")
        res1.save()

        res2, _ = User.objects.get_or_create(
            email="resident2@gmail.com",
            defaults={
                'full_name': 'Ananya Patel',
                'apartment': apt1,
                'flat_number': 'B-501',
                'role': User.Role.RESIDENT,
            }
        )
        res2.set_password("resident123")
        res2.save()

        today = date.today()

        # 3. Create Food Items for Resident 1
        f1, _ = FoodItem.objects.get_or_create(
            user=res1, name="Fresh Cow Milk",
            defaults={
                'category': FoodItem.Category.DAIRY,
                'quantity': Decimal('2.00'),
                'unit': FoodItem.Unit.LITRES,
                'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                'expiry_date': today + timedelta(days=2),
            }
        )

        f2, _ = FoodItem.objects.get_or_create(
            user=res1, name="Organic Fuji Apples",
            defaults={
                'category': FoodItem.Category.FRUITS,
                'quantity': Decimal('1.50'),
                'unit': FoodItem.Unit.KG,
                'storage_location': FoodItem.StorageLocation.PANTRY,
                'expiry_date': today + timedelta(days=6),
            }
        )

        f3, _ = FoodItem.objects.get_or_create(
            user=res1, name="Whole Wheat Sliced Bread",
            defaults={
                'category': FoodItem.Category.BAKERY,
                'quantity': Decimal('1.00'),
                'unit': FoodItem.Unit.PACKET,
                'storage_location': FoodItem.StorageLocation.PANTRY,
                'expiry_date': today + timedelta(days=1),
            }
        )

        # 4. Consumption & Waste Records
        ConsumptionRecord.objects.get_or_create(
            food_item=f2, user=res1,
            defaults={
                'quantity': Decimal('0.50'),
                'unit': 'kg',
                'consumed_at': timezone.now() - timedelta(days=1)
            }
        )

        WasteRecord.objects.get_or_create(
            food_item=f3, user=res1,
            defaults={
                'quantity': Decimal('0.20'),
                'unit': 'packet',
                'reason': WasteRecord.Reason.EXPIRED,
                'description': 'End slices dried out',
                'estimated_value': Decimal('15.00'),
                'wasted_at': timezone.now() - timedelta(days=2)
            }
        )

        # 5. Food Shares
        share1, _ = FoodShare.objects.get_or_create(
            food_item=f1, owner=res1,
            defaults={
                'title': '2L Fresh Unopened Milk',
                'description': 'Bought extra 2L milk pouch today, expires in 2 days.',
                'initial_quantity': Decimal('2.00'),
                'quantity': Decimal('2.00'),
                'unit': 'litres',
                'expires_at': today + timedelta(days=2),
                'status': FoodShare.Status.AVAILABLE,
            }
        )

        # 6. Share Request
        ShareRequest.objects.get_or_create(
            share=share1, requester=res2,
            defaults={
                'quantity': Decimal('1.00'),
                'message': 'Hi Aarav! Can I pick up 1L today around 6 PM?',
                'status': ShareRequest.Status.PENDING,
            }
        )

        # 7. Audit log & Notification
        Notification.objects.get_or_create(
            user=res1,
            title=f"New Request: {share1.title}",
            defaults={
                'food_item': f1,
                'type': Notification.Type.SHARE_REQUEST_RECEIVED,
                'message': f"{res2.full_name} requested 1.0 litres of '{share1.title}'.",
                'priority': Notification.Priority.WARNING,
            }
        )

        ActivityLog.objects.get_or_create(
            user=res1, action='DEMO_DATA_SEEDED',
            defaults={'entity_type': 'System', 'metadata': {'seeded_by': 'seed_demo_data'}}
        )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded demo data: 2 Apartments, Admin '{admin_user.email}', Residents '{res1.email}' & '{res2.email}', Food items, Shares, and Requests."
        ))
