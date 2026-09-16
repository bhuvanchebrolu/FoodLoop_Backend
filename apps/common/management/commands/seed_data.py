from django.core.management.base import BaseCommand
from apps.apartments.models import Apartment
from apps.users.models import CustomUser, UserSettings
from apps.common.utils import log_activity

class Command(BaseCommand):
    help = 'Seeds initial development data for FoodLoop Phase 1 (Apartments, Residents, Admin, Settings, Logs)'

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
        if not CustomUser.objects.filter(email=admin_email).exists():
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

        for rdata in residents_data:
            if not CustomUser.objects.filter(email=rdata['email']).exists():
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

        self.stdout.write(self.style.SUCCESS('Successfully seeded development data for FoodLoop Phase 1!'))
