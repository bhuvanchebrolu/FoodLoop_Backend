from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from datetime import date

class FoodItem(models.Model):
    class Category(models.TextChoices):
        FRUITS = 'FRUITS', 'Fruits'
        VEGETABLES = 'VEGETABLES', 'Vegetables'
        DAIRY = 'DAIRY', 'Dairy'
        MEAT = 'MEAT', 'Meat'
        SEAFOOD = 'SEAFOOD', 'Seafood'
        GRAINS = 'GRAINS', 'Grains'
        BAKERY = 'BAKERY', 'Bakery'
        SNACKS = 'SNACKS', 'Snacks'
        BEVERAGES = 'BEVERAGES', 'Beverages'
        FROZEN = 'FROZEN', 'Frozen'
        PACKAGED = 'PACKAGED', 'Packaged'
        OTHER = 'OTHER', 'Other'

    class Unit(models.TextChoices):
        KG = 'kg', 'kg'
        G = 'g', 'g'
        LITRES = 'litres', 'litres'
        ML = 'ml', 'ml'
        PIECES = 'pieces', 'pieces'
        PACKET = 'packet', 'packet'
        BOX = 'box', 'box'
        CAN = 'can', 'can'
        BOTTLE = 'bottle', 'bottle'
        DOZEN = 'dozen', 'dozen'

    class StorageLocation(models.TextChoices):
        REFRIGERATOR = 'REFRIGERATOR', 'Refrigerator'
        FREEZER = 'FREEZER', 'Freezer'
        PANTRY = 'PANTRY', 'Pantry'
        KITCHEN = 'KITCHEN', 'Kitchen'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        EXPIRING_SOON = 'EXPIRING_SOON', 'Expiring Soon'
        EXPIRED = 'EXPIRED', 'Expired'
        CONSUMED = 'CONSUMED', 'Consumed'
        SHARED = 'SHARED', 'Shared'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='food_items'
    )
    name = models.CharField(max_length=255)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.OTHER
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
        default=Unit.PIECES
    )
    purchase_date = models.DateField(default=date.today)
    expiry_date = models.DateField()
    storage_location = models.CharField(
        max_length=30,
        choices=StorageLocation.choices,
        default=StorageLocation.PANTRY
    )
    estimated_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    photo = models.ImageField(
        upload_to='food_photos/',
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date', 'name']
        verbose_name = 'Food Item'
        verbose_name_plural = 'Food Items'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'expiry_date']),
            models.Index(fields=['user', 'category']),
            models.Index(fields=['user', 'storage_location']),
        ]

    def compute_status(self):
        """
        Determines food status dynamically based on expiry date.
        - Past expiry_date -> EXPIRED
        - 0 to 5 days remaining -> EXPIRING_SOON
        - > 5 days remaining -> AVAILABLE
        """
        if self.status in [self.Status.CONSUMED, self.Status.SHARED]:
            return self.status

        today = date.today()
        if self.expiry_date < today:
            return self.Status.EXPIRED
        elif (self.expiry_date - today).days <= 5:
            return self.Status.EXPIRING_SOON
        else:
            return self.Status.AVAILABLE

    def save(self, *args, **kwargs):
        # Auto-update status based on expiry_date before saving
        self.status = self.compute_status()
        super().save(*args, **kwargs)

    @property
    def days_until_expiry(self):
        return (self.expiry_date - date.today()).days

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit}) - {self.user.email}"
