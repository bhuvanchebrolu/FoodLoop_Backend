from rest_framework import serializers
from .models import Notification
from apps.foods.models import FoodItem
from apps.foods.serializers import FoodItemSerializer

class NotificationSerializer(serializers.ModelSerializer):
    food_name = serializers.ReadOnlyField(source='food_item.name', default=None)

    class Meta:
        model = Notification
        fields = [
            'id',
            'user',
            'food_item',
            'food_name',
            'type',
            'title',
            'message',
            'priority',
            'is_read',
            'created_at',
            'read_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'read_at']


class AlertItemSerializer(serializers.ModelSerializer):
    food = FoodItemSerializer(source='*')
    priority = serializers.SerializerMethodField()
    days_remaining = serializers.ReadOnlyField(source='days_until_expiry')
    urgency_percentage = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = [
            'id',
            'food',
            'name',
            'category',
            'quantity',
            'unit',
            'expiry_date',
            'storage_location',
            'status',
            'days_remaining',
            'priority',
            'urgency_percentage'
        ]

    def get_priority(self, obj):
        if obj.status == FoodItem.Status.EXPIRED or obj.days_until_expiry < 0:
            return 'EXPIRED'
        elif obj.days_until_expiry <= 1:
            return 'URGENT'
        elif obj.days_until_expiry <= 5:
            return 'WARNING'
        else:
            return 'GOOD'

    def get_urgency_percentage(self, obj):
        days = obj.days_until_expiry
        if days <= 0:
            return 100
        elif days >= 14:
            return 10
        else:
            # Scale 14 days down to 1 day -> 10% to 90%
            return min(95, max(15, int(100 - (days / 14.0) * 85)))


class AlertSummarySerializer(serializers.Serializer):
    urgent_count = serializers.IntegerField()
    warning_count = serializers.IntegerField()
    good_count = serializers.IntegerField()
    expired_count = serializers.IntegerField()
    total_alerts = serializers.IntegerField()


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import DeviceToken
        model = DeviceToken
        fields = ['id', 'token', 'device_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at']


class DeviceTokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    device_name = serializers.CharField(required=False, allow_blank=True, default='Browser')

