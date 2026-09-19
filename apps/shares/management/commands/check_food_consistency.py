from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from datetime import date
from apps.foods.models import FoodItem
from apps.shares.models import FoodShare, ShareRequest

class Command(BaseCommand):
    help = 'Audits database consistency for FoodItems, FoodShares, and ShareRequests.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Running FoodLoop Database & Workflow Consistency Audit...'))
        issues = []

        # 1. Negative Quantities
        negative_foods = FoodItem.objects.filter(quantity__lt=Decimal('0.00'))
        if negative_foods.exists():
            issues.append(f"Found {negative_foods.count()} FoodItem(s) with negative quantity.")

        negative_shares = FoodShare.objects.filter(quantity__lt=Decimal('0.00'))
        if negative_shares.exists():
            issues.append(f"Found {negative_shares.count()} FoodShare(s) with negative quantity.")

        negative_requests = ShareRequest.objects.filter(quantity__lt=Decimal('0.00'))
        if negative_requests.exists():
            issues.append(f"Found {negative_requests.count()} ShareRequest(s) with negative quantity.")

        # 2. Over-allocated Food Shares
        for food in FoodItem.objects.all():
            allocated_agg = food.shares.filter(
                status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
            ).aggregate(tot=Sum('quantity'))
            allocated_qty = allocated_agg['tot'] or Decimal('0.00')
            if allocated_qty > food.quantity:
                issues.append(f"FoodItem #{food.id} '{food.name}' is over-allocated: {allocated_qty} shared vs {food.quantity} owned.")

        # 3. Excessive Share Requests
        for share in FoodShare.objects.all():
            for req in share.requests.filter(status=ShareRequest.Status.APPROVED):
                if req.quantity > share.quantity:
                    issues.append(f"Approved ShareRequest #{req.id} quantity ({req.quantity}) exceeds share #{share.id} available quantity ({share.quantity}).")

        # 4. Expired Active Shares
        today = date.today()
        expired_active_shares = FoodShare.objects.filter(
            status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
        ).filter(expires_at__lt=today)
        if expired_active_shares.exists():
            issues.append(f"Found {expired_active_shares.count()} active share(s) past expiration date.")
            # Auto fix expired active shares
            for s in expired_active_shares:
                s.status = FoodShare.Status.EXPIRED
                s.save()

        # Output Audit Results
        if issues:
            self.stdout.write(self.style.ERROR(f"Audit completed with {len(issues)} issue(s) detected:"))
            for issue in issues:
                self.stdout.write(self.style.WARNING(f" - {issue}"))
        else:
            self.stdout.write(self.style.SUCCESS("Database consistency audit passed! All food items, shares, and requests are 100% consistent."))
