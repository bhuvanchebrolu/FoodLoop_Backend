from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import CustomUser, UserSettings
from apps.apartments.models import Apartment
from apps.apartments.serializers import ApartmentSerializer

class UserSerializer(serializers.ModelSerializer):
    apartment = ApartmentSerializer(read_only=True)
    display_apartment_name = serializers.ReadOnlyField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 
            'email', 
            'full_name', 
            'apartment', 
            'apartment_name_custom',
            'display_apartment_name',
            'flat_number', 
            'role',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'email', 'role', 'created_at', 'updated_at']


class ProfileUpdateSerializer(serializers.ModelSerializer):
    apartment_id = serializers.IntegerField(required=False, allow_null=True)
    apartment_name_custom = serializers.CharField(required=False, allow_blank=True, max_length=255)

    class Meta:
        model = CustomUser
        fields = [
            'full_name',
            'flat_number',
            'apartment_id',
            'apartment_name_custom',
        ]

    def update(self, instance, validated_data):
        apartment_id = validated_data.pop('apartment_id', None)
        apartment_name_custom = validated_data.pop('apartment_name_custom', None)

        if apartment_id is not None:
            if apartment_id == 0:
                instance.apartment = None
            else:
                try:
                    instance.apartment = Apartment.objects.get(id=apartment_id)
                except Apartment.DoesNotExist:
                    raise serializers.ValidationError({'apartment_id': 'Invalid apartment selection.'})
        
        if apartment_name_custom is not None:
            instance.apartment_name_custom = apartment_name_custom.strip()
            if not instance.apartment and instance.apartment_name_custom:
                apartment, _ = Apartment.objects.get_or_create(name=instance.apartment_name_custom)
                instance.apartment = apartment

        if 'full_name' in validated_data:
            full_name = validated_data['full_name'].strip()
            if not full_name:
                raise serializers.ValidationError({'full_name': 'Full name cannot be blank.'})
            instance.full_name = full_name

        if 'flat_number' in validated_data:
            instance.flat_number = validated_data['flat_number'].strip()

        instance.save()
        return instance


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            'id',
            'profile_visibility',
            'community_visibility',
            'expiry_notifications',
            'share_notifications',
            'email_notifications',
            'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)
    apartment_id = serializers.IntegerField(required=False, allow_null=True)
    apartment_name_custom = serializers.CharField(required=False, allow_blank=True, max_length=255)

    class Meta:
        model = CustomUser
        fields = [
            'full_name',
            'email',
            'password',
            'confirm_password',
            'apartment_id',
            'apartment_name_custom',
            'flat_number',
        ]

    def validate_email(self, value):
        normalized_email = value.lower().strip()
        if not normalized_email:
            raise serializers.ValidationError("Email is required.")
        if CustomUser.objects.filter(email=normalized_email).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return normalized_email

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        apartment_id = validated_data.pop('apartment_id', None)
        apartment_name_custom = validated_data.pop('apartment_name_custom', '')

        apartment = None
        if apartment_id:
            try:
                apartment = Apartment.objects.get(id=apartment_id)
            except Apartment.DoesNotExist:
                apartment = None
        
        if not apartment and apartment_name_custom.strip():
            apartment, _ = Apartment.objects.get_or_create(name=apartment_name_custom.strip())

        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(
            password=password,
            apartment=apartment,
            apartment_name_custom=apartment_name_custom,
            role=CustomUser.Role.RESIDENT,
            **validated_data
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password', '')

        if not email or not password:
            raise serializers.ValidationError("Both email and password are required.")

        user = authenticate(username=email, password=password)

        if not user:
            if not CustomUser.objects.filter(email=email).exists():
                raise serializers.ValidationError("No account found with this email address.")
            else:
                raise serializers.ValidationError("That email or password doesn't look right.")

        if not user.is_active:
            raise serializers.ValidationError("This user account is currently disabled.")

        attrs['user'] = user
        return attrs
