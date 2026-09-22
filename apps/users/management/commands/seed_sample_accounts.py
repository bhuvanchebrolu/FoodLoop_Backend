from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from apps.apartments.models import Apartment
from apps.users.models import CustomUser, UserSettings
from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.shares.models import FoodShare, ShareRequest
from apps.notifications.models import Notification
from apps.common.models import ActivityLog

class Command(BaseCommand):
    help = 'Seed 5 sample resident accounts, admin account, and rich sample data across all models.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting FoodLoop sample data seeding...'))

        with transaction.atomic():
            # 1. Ensure Apartments Exist
            apt1, _ = Apartment.objects.get_or_create(
                name='Green Valley Eco Towers',
                defaults={'address': '123 Eco Park Way, Green District'}
            )
            apt2, _ = Apartment.objects.get_or_create(
                name='Horizon Heights Residency',
                defaults={'address': '456 Skyline Blvd, Metro City'}
            )
            apt3, _ = Apartment.objects.get_or_create(
                name='Palm Meadows Society',
                defaults={'address': '789 Garden Road, Suburbia'}
            )

            self.stdout.write(self.style.SUCCESS('Apartments verified.'))

            # 2. Seed Admin & 5 Sample Resident Accounts
            accounts_data = [
                {
                    'email': 'admin@gmail.com',
                    'password': 'admin123',
                    'full_name': 'System Administrator',
                    'role': CustomUser.Role.ADMIN,
                    'apartment': apt1,
                    'flat_number': 'A-101',
                },
                {
                    'email': 'resident1@gmail.com',
                    'password': 'password123',
                    'full_name': 'Aarav Sharma',
                    'role': CustomUser.Role.RESIDENT,
                    'apartment': apt1,
                    'flat_number': 'A-102',
                },
                {
                    'email': 'resident2@gmail.com',
                    'password': 'password123',
                    'full_name': 'Priya Patel',
                    'role': CustomUser.Role.RESIDENT,
                    'apartment': apt1,
                    'flat_number': 'A-201',
                },
                {
                    'email': 'resident3@gmail.com',
                    'password': 'password123',
                    'full_name': 'Rohan Gupta',
                    'role': CustomUser.Role.RESIDENT,
                    'apartment': apt1,
                    'flat_number': 'B-104',
                },
                {
                    'email': 'resident4@gmail.com',
                    'password': 'password123',
                    'full_name': 'Ananya Reddy',
                    'role': CustomUser.Role.RESIDENT,
                    'apartment': apt2,
                    'flat_number': 'H-302',
                },
                {
                    'email': 'resident5@gmail.com',
                    'password': 'password123',
                    'full_name': 'Vikram Malhotra',
                    'role': CustomUser.Role.RESIDENT,
                    'apartment': apt2,
                    'flat_number': 'H-405',
                }
            ]

            users = {}
            for acc in accounts_data:
                user, created = CustomUser.objects.get_or_create(
                    email=acc['email'],
                    defaults={
                        'username': acc['email'],
                        'full_name': acc['full_name'],
                        'role': acc['role'],
                        'apartment': acc['apartment'],
                        'flat_number': acc['flat_number'],
                        'is_staff': (acc['role'] == CustomUser.Role.ADMIN),
                        'is_superuser': (acc['role'] == CustomUser.Role.ADMIN),
                    }
                )
                user.set_password(acc['password'])
                user.role = acc['role']
                user.apartment = acc['apartment']
                user.flat_number = acc['flat_number']
                user.is_staff = (acc['role'] == CustomUser.Role.ADMIN)
                user.is_superuser = (acc['role'] == CustomUser.Role.ADMIN)
                user.save()

                # Ensure UserSettings exists
                UserSettings.objects.get_or_create(user=user)
                users[acc['email']] = user

            # Also ensure any other test users in DB belong to apt1 so they see all shares
            other_users = CustomUser.objects.filter(apartment__isnull=True)
            for u in other_users:
                u.apartment = apt1
                u.flat_number = u.flat_number or 'A-303'
                u.save()

            self.stdout.write(self.style.SUCCESS('User accounts & settings created.'))

            # 3. Seed Food Items for Users
            today = date.today()
            
            food_items_def = [
                # Resident 1
                {
                    'user': users['resident1@gmail.com'],
                    'name': 'Organic Alphonso Mangoes',
                    'category': FoodItem.Category.FRUITS,
                    'quantity': Decimal('3.00'),
                    'unit': FoodItem.Unit.KG,
                    'expiry_date': today + timedelta(days=5),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('15.00')
                },
                {
                    'user': users['resident1@gmail.com'],
                    'name': 'Farm Fresh Whole Milk',
                    'category': FoodItem.Category.DAIRY,
                    'quantity': Decimal('2.00'),
                    'unit': FoodItem.Unit.LITRES,
                    'expiry_date': today + timedelta(days=2),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('4.50')
                },
                {
                    'user': users['resident1@gmail.com'],
                    'name': 'Whole Wheat Sourdough Bread',
                    'category': FoodItem.Category.BAKERY,
                    'quantity': Decimal('2.00'),
                    'unit': FoodItem.Unit.PIECES,
                    'expiry_date': today + timedelta(days=3),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('6.00')
                },
                {
                    'user': users['resident1@gmail.com'],
                    'name': 'Organic Baby Spinach',
                    'category': FoodItem.Category.VEGETABLES,
                    'quantity': Decimal('250.00'),
                    'unit': FoodItem.Unit.G,
                    'expiry_date': today + timedelta(days=1),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('3.20')
                },

                # Resident 2
                {
                    'user': users['resident2@gmail.com'],
                    'name': 'Greek Vanilla Yogurt 1kg',
                    'category': FoodItem.Category.DAIRY,
                    'quantity': Decimal('1.00'),
                    'unit': FoodItem.Unit.KG,
                    'expiry_date': today + timedelta(days=4),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('5.50')
                },
                {
                    'user': users['resident2@gmail.com'],
                    'name': 'Crisp Gala Apples',
                    'category': FoodItem.Category.FRUITS,
                    'quantity': Decimal('4.00'),
                    'unit': FoodItem.Unit.KG,
                    'expiry_date': today + timedelta(days=8),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('8.00')
                },
                {
                    'user': users['resident2@gmail.com'],
                    'name': 'Artisan Butter Croissants',
                    'category': FoodItem.Category.BAKERY,
                    'quantity': Decimal('6.00'),
                    'unit': FoodItem.Unit.PIECES,
                    'expiry_date': today + timedelta(days=2),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('7.50')
                },
                {
                    'user': users['resident2@gmail.com'],
                    'name': 'Free Range Eggs',
                    'category': FoodItem.Category.OTHER,
                    'quantity': Decimal('12.00'),
                    'unit': FoodItem.Unit.PIECES,
                    'expiry_date': today + timedelta(days=12),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('4.80')
                },

                # Resident 3
                {
                    'user': users['resident3@gmail.com'],
                    'name': 'Hass Avocados 4-pack',
                    'category': FoodItem.Category.FRUITS,
                    'quantity': Decimal('4.00'),
                    'unit': FoodItem.Unit.PIECES,
                    'expiry_date': today + timedelta(days=5),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('6.00')
                },
                {
                    'user': users['resident3@gmail.com'],
                    'name': 'Cheddar Cheese Block 500g',
                    'category': FoodItem.Category.DAIRY,
                    'quantity': Decimal('1.00'),
                    'unit': FoodItem.Unit.PACKET,
                    'expiry_date': today + timedelta(days=15),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('6.50')
                },
                {
                    'user': users['resident3@gmail.com'],
                    'name': 'Brown Basmati Rice 5kg',
                    'category': FoodItem.Category.GRAINS,
                    'quantity': Decimal('5.00'),
                    'unit': FoodItem.Unit.KG,
                    'expiry_date': today + timedelta(days=90),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('12.00')
                },
                {
                    'user': users['resident3@gmail.com'],
                    'name': 'Dark Chocolate 85% Bar',
                    'category': FoodItem.Category.SNACKS,
                    'quantity': Decimal('3.00'),
                    'unit': FoodItem.Unit.PIECES,
                    'expiry_date': today + timedelta(days=45),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('7.00')
                },

                # Resident 4
                {
                    'user': users['resident4@gmail.com'],
                    'name': 'Frozen Sweet Corn 1kg',
                    'category': FoodItem.Category.FROZEN,
                    'quantity': Decimal('1.00'),
                    'unit': FoodItem.Unit.KG,
                    'expiry_date': today + timedelta(days=60),
                    'storage_location': FoodItem.StorageLocation.FREEZER,
                    'estimated_value': Decimal('3.80')
                },
                {
                    'user': users['resident4@gmail.com'],
                    'name': 'Almond Milk Unsweetened',
                    'category': FoodItem.Category.BEVERAGES,
                    'quantity': Decimal('2.00'),
                    'unit': FoodItem.Unit.LITRES,
                    'expiry_date': today + timedelta(days=4),
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('5.00')
                },

                # Resident 5
                {
                    'user': users['resident5@gmail.com'],
                    'name': 'Fresh Strawberries Box',
                    'category': FoodItem.Category.FRUITS,
                    'quantity': Decimal('1.00'),
                    'unit': FoodItem.Unit.BOX,
                    'expiry_date': today - timedelta(days=1), # Expired!
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': Decimal('4.50')
                },
                {
                    'user': users['resident5@gmail.com'],
                    'name': 'Organic Tomatoes',
                    'category': FoodItem.Category.VEGETABLES,
                    'quantity': Decimal('2.00'),
                    'unit': FoodItem.Unit.KG,
                    'expiry_date': today + timedelta(days=6),
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': Decimal('3.50')
                }
            ]

            created_food_items = []
            for item in food_items_def:
                fi, _ = FoodItem.objects.get_or_create(
                    user=item['user'],
                    name=item['name'],
                    defaults={
                        'category': item['category'],
                        'quantity': item['quantity'],
                        'unit': item['unit'],
                        'expiry_date': item['expiry_date'],
                        'storage_location': item['storage_location'],
                        'estimated_value': item['estimated_value'],
                    }
                )
                created_food_items.append(fi)

            self.stdout.write(self.style.SUCCESS(f'{len(created_food_items)} Food items created/verified.'))

            # 4. Seed Community Food Shares
            shares_def = [
                {
                    'food_item': created_food_items[0], # Alphonso Mangoes
                    'owner': users['resident1@gmail.com'],
                    'title': 'Fresh Organic Alphonso Mangoes (1kg)',
                    'description': 'Bought extra carton from organic market. Sweet and fragrant!',
                    'initial_quantity': Decimal('1.00'),
                    'quantity': Decimal('1.00'),
                    'unit': 'kg',
                    'visibility': FoodShare.Visibility.APARTMENT,
                    'pickup_note': 'Available evenings after 5 PM. Flat A-102.'
                },
                {
                    'food_item': created_food_items[2], # Sourdough Bread
                    'owner': users['resident1@gmail.com'],
                    'title': 'Whole Wheat Sourdough Bread',
                    'description': 'Freshly baked sourdough, 1 full loaf available.',
                    'initial_quantity': Decimal('1.00'),
                    'quantity': Decimal('1.00'),
                    'unit': 'pieces',
                    'visibility': FoodShare.Visibility.APARTMENT,
                    'pickup_note': 'Leave message or ring doorbell at A-102.'
                },
                {
                    'food_item': created_food_items[4], # Greek Yogurt
                    'owner': users['resident2@gmail.com'],
                    'title': 'Greek Vanilla Yogurt (Unopened 500g)',
                    'description': 'Unopened tub, expiring in 4 days. Free for neighbors.',
                    'initial_quantity': Decimal('0.50'),
                    'quantity': Decimal('0.50'),
                    'unit': 'kg',
                    'visibility': FoodShare.Visibility.APARTMENT,
                    'pickup_note': 'Flat A-201, any time before 9 PM.'
                },
                {
                    'food_item': created_food_items[6], # Croissants
                    'owner': users['resident2@gmail.com'],
                    'title': 'Fresh Bakery Butter Croissants (3 pcs)',
                    'description': 'Crispy fresh croissants from French bakery.',
                    'initial_quantity': Decimal('3.00'),
                    'quantity': Decimal('3.00'),
                    'unit': 'pieces',
                    'visibility': FoodShare.Visibility.NEIGHBOURS,
                    'pickup_note': 'Flat A-201.'
                },
                {
                    'food_item': created_food_items[8], # Avocados
                    'owner': users['resident3@gmail.com'],
                    'title': 'Ripe Hass Avocados (2 pcs)',
                    'description': 'Perfectly ripe for guacamole today or tomorrow.',
                    'initial_quantity': Decimal('2.00'),
                    'quantity': Decimal('2.00'),
                    'unit': 'pieces',
                    'visibility': FoodShare.Visibility.APARTMENT,
                    'pickup_note': 'Flat B-104.'
                },
                {
                    'food_item': created_food_items[11], # Dark Chocolate
                    'owner': users['resident3@gmail.com'],
                    'title': 'Dark Chocolate 85% Cocoa Bar',
                    'description': 'Sealed dark chocolate bar.',
                    'initial_quantity': Decimal('1.00'),
                    'quantity': Decimal('1.00'),
                    'unit': 'pieces',
                    'visibility': FoodShare.Visibility.APARTMENT,
                    'pickup_note': 'Flat B-104.'
                },
                {
                    'food_item': created_food_items[13], # Almond Milk
                    'owner': users['resident4@gmail.com'],
                    'title': 'Unsweetened Almond Milk 1L',
                    'description': 'Unopened carton of organic almond milk.',
                    'initial_quantity': Decimal('1.00'),
                    'quantity': Decimal('1.00'),
                    'unit': 'litres',
                    'visibility': FoodShare.Visibility.APARTMENT,
                    'pickup_note': 'Flat H-302, Horizon Heights.'
                }
            ]

            created_shares = []
            for s in shares_def:
                share, _ = FoodShare.objects.get_or_create(
                    food_item=s['food_item'],
                    owner=s['owner'],
                    title=s['title'],
                    defaults={
                        'description': s['description'],
                        'initial_quantity': s['initial_quantity'],
                        'quantity': s['quantity'],
                        'unit': s['unit'],
                        'visibility': s['visibility'],
                        'pickup_note': s['pickup_note'],
                        'expires_at': s['food_item'].expiry_date,
                    }
                )
                created_shares.append(share)

            self.stdout.write(self.style.SUCCESS(f'{len(created_shares)} Food Shares created.'))

            # 5. Seed Share Requests
            if len(created_shares) >= 3:
                # Request 1: Resident 2 requests Resident 1's Mangoes (Approved)
                req1, _ = ShareRequest.objects.get_or_create(
                    share=created_shares[0],
                    requester=users['resident2@gmail.com'],
                    defaults={
                        'quantity': Decimal('1.00'),
                        'message': 'Hi Aarav! Would love the mangoes for smoothie. Can pick up at 6 PM.',
                        'status': ShareRequest.Status.APPROVED
                    }
                )

                # Request 2: Resident 3 requests Resident 1's Mangoes (Pending)
                req2, _ = ShareRequest.objects.get_or_create(
                    share=created_shares[0],
                    requester=users['resident3@gmail.com'],
                    defaults={
                        'quantity': Decimal('1.00'),
                        'message': 'Hey, are the mangoes still available?',
                        'status': ShareRequest.Status.PENDING
                    }
                )

                # Request 3: Resident 1 requests Resident 2's Yogurt (Completed)
                req3, _ = ShareRequest.objects.get_or_create(
                    share=created_shares[2],
                    requester=users['resident1@gmail.com'],
                    defaults={
                        'quantity': Decimal('0.50'),
                        'message': 'Thanks Priya! Picked up the yogurt.',
                        'status': ShareRequest.Status.COMPLETED
                    }
                )

            self.stdout.write(self.style.SUCCESS('Share Requests created.'))

            # 6. Seed Consumption & Waste Records for Analytics
            for u in users.values():
                # Consumption records
                ConsumptionRecord.objects.get_or_create(
                    user=u,
                    food_item=created_food_items[0],
                    defaults={
                        'quantity': Decimal('1.00'),
                        'unit': 'kg',
                        'consumed_at': timezone.now() - timedelta(days=1)
                    }
                )
                ConsumptionRecord.objects.get_or_create(
                    user=u,
                    food_item=created_food_items[1],
                    defaults={
                        'quantity': Decimal('0.50'),
                        'unit': 'litres',
                        'consumed_at': timezone.now() - timedelta(days=2)
                    }
                )

                # Waste records
                WasteRecord.objects.get_or_create(
                    user=u,
                    food_item=created_food_items[14], # Strawberries
                    defaults={
                        'quantity': Decimal('0.50'),
                        'unit': 'box',
                        'reason': WasteRecord.Reason.EXPIRED,
                        'estimated_value': Decimal('2.25'),
                        'description': 'Forgotten in back of fridge.',
                        'wasted_at': timezone.now() - timedelta(days=1)
                    }
                )

            self.stdout.write(self.style.SUCCESS('Analytics consumption & waste records created.'))

            # 7. Seed Notifications & Activity Logs
            for u in users.values():
                Notification.objects.get_or_create(
                    user=u,
                    title='Welcome to FoodLoop!',
                    defaults={
                        'message': 'Your account is active. Start adding pantry items or sharing surplus food with neighbors.',
                        'type': Notification.Type.SYSTEM,
                        'priority': Notification.Priority.GOOD
                    }
                )
                Notification.objects.get_or_create(
                    user=u,
                    title='Expiry Alert: Organic Baby Spinach',
                    defaults={
                        'message': 'Organic Baby Spinach expires tomorrow! Share or consume it to prevent food waste.',
                        'type': Notification.Type.EXPIRY_WARNING,
                        'priority': Notification.Priority.WARNING
                    }
                )

                ActivityLog.objects.create(
                    user=u,
                    action='USER_LOGIN',
                    entity_type='User',
                    entity_id=u.id,
                    metadata={'ip': '127.0.0.1'}
                )

            self.stdout.write(self.style.SUCCESS('Notifications & Activity Logs created.'))

        self.stdout.write(self.style.SUCCESS('All FoodLoop sample accounts and data successfully seeded!'))
