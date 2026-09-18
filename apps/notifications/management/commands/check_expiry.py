from django.core.management.base import BaseCommand
from apps.notifications.services import ExpiryEngineService

class Command(BaseCommand):
    help = 'Executes background expiry engine check to update food statuses and generate notifications'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running FoodLoop Expiry Engine...'))
        count = ExpiryEngineService.check_and_generate_expiry_notifications()
        self.stdout.write(self.style.SUCCESS(f'Successfully processed expiry engine. Generated {count} new notification(s).'))
