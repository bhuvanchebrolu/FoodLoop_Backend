from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.apartments.models import Apartment

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('username', email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', CustomUser.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        RESIDENT = 'RESIDENT', 'Resident'
        ADMIN = 'ADMIN', 'Admin'

    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    apartment = models.ForeignKey(
        Apartment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='residents'
    )
    apartment_name_custom = models.CharField(max_length=255, blank=True, default='')
    flat_number = models.CharField(max_length=50, blank=True, default='')
    role = models.CharField(
        max_length=20, 
        choices=Role.choices, 
        default=Role.RESIDENT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.full_name} ({self.email}) [{self.role}]"

    @property
    def display_apartment_name(self):
        if self.apartment:
            return self.apartment.name
        elif self.apartment_name_custom:
            return self.apartment_name_custom
        return 'Independent Resident'


class UserSettings(models.Model):
    class ProfileVisibility(models.TextChoices):
        COMMUNITY = 'COMMUNITY', 'Community'
        APARTMENT = 'APARTMENT', 'Apartment'
        PRIVATE = 'PRIVATE', 'Private'

    class CommunityVisibility(models.TextChoices):
        APARTMENT = 'APARTMENT', 'Apartment'
        ALL = 'ALL', 'All'
        PRIVATE = 'PRIVATE', 'Private'

    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='settings'
    )
    profile_visibility = models.CharField(
        max_length=20, 
        choices=ProfileVisibility.choices, 
        default=ProfileVisibility.COMMUNITY
    )
    community_visibility = models.CharField(
        max_length=20, 
        choices=CommunityVisibility.choices, 
        default=CommunityVisibility.APARTMENT
    )
    expiry_notifications = models.BooleanField(default=True)
    share_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Settings'
        verbose_name_plural = 'User Settings'

    def __str__(self):
        return f"Settings for {self.user.email}"


@receiver(post_save, sender=CustomUser)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.get_or_create(user=instance)
