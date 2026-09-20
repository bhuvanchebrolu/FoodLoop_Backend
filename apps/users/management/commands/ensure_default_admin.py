import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.apartments.models import Apartment

User = get_user_model()

class Command(BaseCommand):
    help = 'Ensures the fixed default admin account specified in .env exists and has ADMIN role & password'

    def handle(self, *args, **options):
        email = os.getenv('ADMIN_EMAIL', 'admin@gmail.com').strip().lower()
        password = os.getenv('ADMIN_PASSWORD', 'admin123').strip()
        full_name = 'System Administrator'

        apartment, _ = Apartment.objects.get_or_create(name='FoodLoop Central Admin')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'full_name': full_name,
                'apartment': apartment,
                'flat_number': 'ADMIN-1',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )

        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if not user.apartment:
            user.apartment = apartment
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"Successfully {action} fixed admin account: Email='{email}', Password='{password}', Role='{user.role}'"
        ))
