from django.db import models
from django.conf import settings

class Report(models.Model):
    class TargetType(models.TextChoices):
        FOOD_SHARE = 'FOOD_SHARE', 'Food Share'
        USER = 'USER', 'User'
        FOOD_ITEM = 'FOOD_ITEM', 'Food Item'

    class Reason(models.TextChoices):
        INAPPROPRIATE_CONTENT = 'INAPPROPRIATE_CONTENT', 'Inappropriate Content'
        MISLEADING_LISTING = 'MISLEADING_LISTING', 'Misleading Listing'
        SPAM = 'SPAM', 'Spam / Advertising'
        HARASSMENT = 'HARASSMENT', 'Harassment or Abuse'
        DUPLICATE = 'DUPLICATE', 'Duplicate Content'
        OTHER = 'OTHER', 'Other Concern'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        RESOLVED = 'RESOLVED', 'Resolved'
        DISMISSED = 'DISMISSED', 'Dismissed'

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_submitted'
    )
    target_type = models.CharField(
        max_length=30,
        choices=TargetType.choices,
        default=TargetType.FOOD_SHARE
    )
    target_id = models.CharField(max_length=100)
    reason = models.CharField(
        max_length=50,
        choices=Reason.choices,
        default=Reason.OTHER
    )
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_reviewed'
    )
    resolution_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['reporter']),
        ]

    def __str__(self):
        reporter_email = self.reporter.email if self.reporter else "Anonymous"
        return f"Report #{self.id} [{self.status}] by {reporter_email} on {self.target_type}:{self.target_id}"
