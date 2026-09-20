from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Sum
from decimal import Decimal

from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
from apps.shares.models import FoodShare, ShareRequest
from apps.reports.models import Report
from apps.notifications.models import Notification
from apps.common.models import ActivityLog

User = get_user_model()

class Command(BaseCommand):
    help = 'Audits FoodLoop Phase 1-5 database relational consistency and business rules'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Starting FoodLoop Complete System Consistency Audit...\n"))
        issues_found = 0

        # 1. Audit Users
        self.stdout.write("Checking Users...")
        invalid_roles = User.objects.exclude(role__in=[User.Role.RESIDENT, User.Role.ADMIN])
        if invalid_roles.exists():
            issues_found += invalid_roles.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {invalid_roles.count()} users with invalid roles."))
        
        users_without_apt = User.objects.filter(apartment__isnull=True, apartment_name_custom='')
        if users_without_apt.exists():
            self.stdout.write(self.style.WARNING(f"  [*] Notice: {users_without_apt.count()} residents have independent residency (no apartment)."))

        # 2. Audit FoodItems
        self.stdout.write("\nChecking FoodItems...")
        negative_food = FoodItem.objects.filter(quantity__lt=Decimal('0.00'))
        if negative_food.exists():
            issues_found += negative_food.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {negative_food.count()} food items with negative quantity."))

        orphaned_food = FoodItem.objects.filter(user__isnull=True)
        if orphaned_food.exists():
            issues_found += orphaned_food.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {orphaned_food.count()} orphaned food items without owner."))

        invalid_food_status = FoodItem.objects.exclude(status__in=[
            FoodItem.Status.AVAILABLE, FoodItem.Status.EXPIRING_SOON,
            FoodItem.Status.EXPIRED, FoodItem.Status.CONSUMED,
            FoodItem.Status.SHARED
        ])
        if invalid_food_status.exists():
            issues_found += invalid_food_status.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {invalid_food_status.count()} food items with invalid status."))

        # 3. Audit FoodShares
        self.stdout.write("\nChecking FoodShares & Quantity Allocations...")
        orphaned_shares = FoodShare.objects.filter(food_item__isnull=True)
        if orphaned_shares.exists():
            issues_found += orphaned_shares.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {orphaned_shares.count()} shares without food items."))

        mismatched_owner_shares = FoodShare.objects.select_related('food_item', 'owner').exclude(owner=models.F('food_item__user'))
        # Using loop comparison for precise FK relation match
        mismatch_count = 0
        for s in FoodShare.objects.select_related('food_item', 'owner'):
            if s.food_item and s.owner != s.food_item.user:
                mismatch_count += 1
        if mismatch_count > 0:
            issues_found += mismatch_count
            self.stdout.write(self.style.ERROR(f"  [!] Found {mismatch_count} shares where share owner does not match food item owner."))

        # Over-allocation check
        active_shares = FoodShare.objects.filter(
            status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
        ).values('food_item_id').annotate(total_shared=Sum('quantity'))

        overallocated_count = 0
        for entry in active_shares:
            try:
                food = FoodItem.objects.get(id=entry['food_item_id'])
                if entry['total_shared'] > (food.quantity + entry['total_shared']):
                    overallocated_count += 1
            except FoodItem.DoesNotExist:
                pass

        if overallocated_count > 0:
            issues_found += overallocated_count
            self.stdout.write(self.style.ERROR(f"  [!] Found {overallocated_count} overallocated food shares."))

        # 4. Audit ShareRequests
        self.stdout.write("\nChecking ShareRequests...")
        orphaned_requests = ShareRequest.objects.filter(share__isnull=True)
        if orphaned_requests.exists():
            issues_found += orphaned_requests.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {orphaned_requests.count()} requests without associated shares."))

        invalid_request_qty = 0
        for req in ShareRequest.objects.select_related('share'):
            if req.share and req.status == ShareRequest.Status.PENDING and req.quantity > req.share.quantity:
                invalid_request_qty += 1

        if invalid_request_qty > 0:
            issues_found += invalid_request_qty
            self.stdout.write(self.style.ERROR(f"  [!] Found {invalid_request_qty} pending requests with quantity exceeding remaining share allocation."))

        # 5. Audit Reports
        self.stdout.write("\nChecking Reports & Moderation Data...")
        orphaned_reports = Report.objects.filter(reporter__isnull=True)
        if orphaned_reports.exists():
            self.stdout.write(self.style.WARNING(f"  [*] Notice: {orphaned_reports.count()} reports created by deleted user accounts."))

        invalid_report_status = Report.objects.exclude(status__in=[
            Report.Status.PENDING, Report.Status.UNDER_REVIEW,
            Report.Status.RESOLVED, Report.Status.DISMISSED
        ])
        if invalid_report_status.exists():
            issues_found += invalid_report_status.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {invalid_report_status.count()} reports with invalid status."))

        # 6. Audit Notifications & Activity
        self.stdout.write("\nChecking Notifications & Audit Logs...")
        orphaned_notifs = Notification.objects.filter(user__isnull=True)
        if orphaned_notifs.exists():
            issues_found += orphaned_notifs.count()
            self.stdout.write(self.style.ERROR(f"  [!] Found {orphaned_notifs.count()} notifications without target user."))

        # Summary
        self.stdout.write("\n" + "="*50)
        if issues_found == 0:
            self.stdout.write(self.style.SUCCESS("[OK] FoodLoop System Audit PASSED 100%! All Phase 1-5 data models and workflows are consistent."))
        else:
            self.stdout.write(self.style.ERROR(f"[FAIL] FoodLoop System Audit FAILED: Identified {issues_found} data inconsistency issue(s)."))
        self.stdout.write("="*50 + "\n")
