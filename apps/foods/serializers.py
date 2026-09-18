from rest_framework import serializers
from .models import FoodItem, ConsumptionRecord, WasteRecord
from datetime import date

class FoodItemSerializer(serializers.ModelSerializer):
    days_until_expiry = serializers.ReadOnlyField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = [
            'id',
            'user',
            'name',
            'category',
            'quantity',
            'unit',
            'purchase_date',
            'expiry_date',
            'storage_location',
            'estimated_value',
            'photo',
            'photo_url',
            'status',
            'days_until_expiry',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'status', 'created_at', 'updated_at', 'days_until_expiry', 'photo_url']

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate(self, attrs):
        purchase_date = attrs.get('purchase_date') or (self.instance.purchase_date if self.instance else None)
        expiry_date = attrs.get('expiry_date') or (self.instance.expiry_date if self.instance else None)

        if purchase_date and expiry_date and expiry_date < purchase_date:
            raise serializers.ValidationError({
                "expiry_date": "Expiry date cannot be earlier than purchase date."
            })
        return attrs


class ConsumptionRecordSerializer(serializers.ModelSerializer):
    food_name = serializers.ReadOnlyField(source='food_item.name')

    class Meta:
        model = ConsumptionRecord
        fields = [
            'id',
            'food_item',
            'food_name',
            'user',
            'quantity',
            'unit',
            'consumed_at',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class ConsumeActionSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Consumed quantity must be greater than zero.")
        return value


class WasteRecordSerializer(serializers.ModelSerializer):
    food_name = serializers.ReadOnlyField(source='food_item.name')

    class Meta:
        model = WasteRecord
        fields = [
            'id',
            'food_item',
            'food_name',
            'user',
            'quantity',
            'unit',
            'reason',
            'description',
            'estimated_value',
            'wasted_at',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class WasteActionSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    reason = serializers.ChoiceField(choices=WasteRecord.Reason.choices, default=WasteRecord.Reason.EXPIRED)
    description = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Wasted quantity must be greater than zero.")
        return value


class FoodDashboardSerializer(serializers.Serializer):
    total_food_items = serializers.IntegerField()
    available_items = serializers.IntegerField()
    expiring_soon = serializers.IntegerField()
    expired_items = serializers.IntegerField()
    consumed_items = serializers.IntegerField()
    total_estimated_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    category_counts = serializers.DictField()
    storage_counts = serializers.DictField()
