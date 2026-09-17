from django.core.management.base import BaseCommand
from datetime import date, timedelta
from apps.apartments.models import Apartment
from apps.users.models import CustomUser, UserSettings
from apps.foods.models import FoodItem
from apps.common.utils import log_activity

class Command(BaseCommand):
    help = 'Seeds initial development data for FoodLoop Phase 1 & Phase 2 (Apartments, Residents, Admin, Food Items)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding FoodLoop development data...'))

        # 1. Create Apartments
        apartments_data = [
            {'name': 'Green Heights', 'address': '124 Eco Park Avenue, Green District'},
            {'name': 'Sunrise Apartments', 'address': '88 Sunshine Boulevard, East Wing'},
            {'name': 'Palm Grove', 'address': '45 Palm Grove Way, West End'},
        ]

        created_apartments = []
        for apt in apartments_data:
            obj, created = Apartment.objects.get_or_create(
                name=apt['name'],
                defaults={'address': apt['address']}
            )
            created_apartments.append(obj)
            status_str = 'Created' if created else 'Already exists'
            self.stdout.write(f"Apartment '{obj.name}': {status_str}")

        green_heights = created_apartments[0]
        sunrise = created_apartments[1]

        # 2. Create Admin User
        admin_email = 'admin@foodloop.com'
        admin_user = CustomUser.objects.filter(email=admin_email).first()
        if not admin_user:
            admin_user = CustomUser.objects.create_superuser(
                email=admin_email,
                password='Password123!',
                full_name='FoodLoop Admin',
                apartment=green_heights,
                flat_number='A-101',
                role=CustomUser.Role.ADMIN
            )
            log_activity(admin_user, 'USER_REGISTERED', 'User', admin_user.id, {'role': 'ADMIN'})
            self.stdout.write(self.style.SUCCESS(f"Created Admin user: {admin_email} (Password: Password123!)"))
        else:
            self.stdout.write(f"Admin user {admin_email} already exists.")

        # 3. Create Resident Users
        residents_data = [
            {
                'email': 'sarah@foodloop.com',
                'full_name': 'Sarah Jenkins',
                'apartment': green_heights,
                'flat_number': 'B-204',
                'password': 'Password123!'
            },
            {
                'email': 'alex@foodloop.com',
                'full_name': 'Alex Rivera',
                'apartment': green_heights,
                'flat_number': 'A-302',
                'password': 'Password123!'
            },
            {
                'email': 'priya@foodloop.com',
                'full_name': 'Priya Sharma',
                'apartment': sunrise,
                'flat_number': 'C-105',
                'password': 'Password123!'
            }
        ]

        created_residents = {}
        for rdata in residents_data:
            user = CustomUser.objects.filter(email=rdata['email']).first()
            if not user:
                user = CustomUser.objects.create_user(
                    email=rdata['email'],
                    password=rdata['password'],
                    full_name=rdata['full_name'],
                    apartment=rdata['apartment'],
                    flat_number=rdata['flat_number'],
                    role=CustomUser.Role.RESIDENT
                )
                log_activity(user, 'USER_REGISTERED', 'User', user.id, {'role': 'RESIDENT'})
                self.stdout.write(self.style.SUCCESS(f"Created Resident user: {user.email} (Password: Password123!)"))
            else:
                self.stdout.write(f"Resident user {rdata['email']} already exists.")
            created_residents[rdata['email']] = user

        # 4. Seed Phase 2 Food Items for Sarah Jenkins
        sarah = created_residents.get('sarah@foodloop.com')
        if sarah and not FoodItem.objects.filter(user=sarah).exists():
            today = date.today()
            sample_foods = [
                {
                    'name': 'Organic Whole Milk',
                    'category': FoodItem.Category.DAIRY,
                    'quantity': 2.0,
                    'unit': FoodItem.Unit.LITRES,
                    'purchase_date': today - timedelta(days=2),
                    'expiry_date': today + timedelta(days=2), # Expiring Soon
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': 4.50
                },
                {
                    'name': 'Fresh Apples',
                    'category': FoodItem.Category.FRUITS,
                    'quantity': 6.0,
                    'unit': FoodItem.Unit.PIECES,
                    'purchase_date': today - timedelta(days=4),
                    'expiry_date': today + timedelta(days=10), # Available
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': 3.20
                },
                {
                    'name': 'Whole Grain Bread',
                    'category': FoodItem.Category.BAKERY,
                    'quantity': 1.0,
                    'unit': FoodItem.Unit.PACKET,
                    'purchase_date': today - timedelta(days=5),
                    'expiry_date': today - timedelta(days=1), # Expired
                    'storage_location': FoodItem.StorageLocation.PANTRY,
                    'estimated_value': 2.80
                },
                {
                    'name': 'Greek Yogurt',
                    'category': FoodItem.Category.DAIRY,
                    'quantity': 500.0,
                    'unit': FoodItem.Unit.G,
                    'purchase_date': today - timedelta(days=1),
                    'expiry_date': today + timedelta(days=4), # Expiring Soon
                    'storage_location': FoodItem.StorageLocation.REFRIGERATOR,
                    'estimated_value': 5.00
                },
                {
                    'name': 'Frozen Blueberries',
                    'category': FoodItem.Category.FROZEN,
                    'quantity': 1.0,
                    'unit': FoodItem.Unit.PACKET,
                    'purchase_date': today - timedelta(days=10),
                    'expiry_date': today + timedelta(days=60), # Available
                    'storage_location': FoodItem.StorageLocation.FREEZER,
                    'estimated_value': 6.90
                }
            ]

            for fdata in sample_foods:
                item = FoodItem.objects.create(user=sarah, **fdata)
                log_activity(sarah, 'FOOD_ADDED', 'FoodItem', item.id, {'name': item.name})
            self.stdout.write(self.style.SUCCESS(f"Seeded {len(sample_foods)} sample food items for Sarah Jenkins."))

        self.stdout.write(self.style.SUCCESS('Successfully seeded development data for FoodLoop Phase 1 & 2!'))
