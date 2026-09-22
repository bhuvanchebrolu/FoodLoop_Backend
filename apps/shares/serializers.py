from rest_framework import serializers
from decimal import Decimal
from datetime import date
from django.db.models import Sum
from .models import FoodShare, ShareRequest, SavedShare
from apps.foods.models import FoodItem

class FoodShareSerializer(serializers.ModelSerializer):
    food_name = serializers.ReadOnlyField(source='food_item.name')
    food_category = serializers.ReadOnlyField(source='food_item.category')
    food_photo_url = serializers.SerializerMethodField()
    expiry_date = serializers.ReadOnlyField(source='food_item.expiry_date')
    owner = serializers.SerializerMethodField()
    owner_name = serializers.ReadOnlyField(source='owner.full_name')
    owner_flat = serializers.ReadOnlyField(source='owner.flat_number')
    owner_apartment = serializers.ReadOnlyField(source='owner.display_apartment_name')
    is_owner = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    pending_requests_count = serializers.SerializerMethodField()
    user_request = serializers.SerializerMethodField()
    has_active_request = serializers.SerializerMethodField()
    requests = serializers.SerializerMethodField()

    class Meta:
        model = FoodShare
        fields = [
            'id',
            'food_item',
            'owner',
            'title',
            'description',
            'initial_quantity',
            'quantity',
            'unit',
            'visibility',
            'status',
            'pickup_note',
            'expires_at',
            'created_at',
            'updated_at',
            'food_name',
            'food_category',
            'food_photo_url',
            'expiry_date',
            'owner_name',
            'owner_flat',
            'owner_apartment',
            'is_owner',
            'is_saved',
            'pending_requests_count',
            'user_request',
            'has_active_request',
            'requests'
        ]
        read_only_fields = ['id', 'owner', 'status', 'created_at', 'updated_at']

    def get_owner(self, obj):
        if obj.owner:
            return {
                'id': obj.owner.id,
                'full_name': obj.owner.full_name,
                'email': obj.owner.email,
                'flat_number': obj.owner.flat_number,
                'apartment': obj.owner.display_apartment_name
            }
        return None

    def get_food_photo_url(self, obj):
        if obj.food_item and obj.food_item.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.food_item.photo.url)
            return obj.food_item.photo.url
        return None

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.owner_id == request.user.id
        return False

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedShare.objects.filter(user=request.user, share=obj).exists()
        return False

    def get_pending_requests_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.owner_id == request.user.id:
            return obj.requests.filter(status=ShareRequest.Status.PENDING).count()
        return 0

    def get_user_request(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            req = obj.requests.filter(requester=request.user).exclude(
                status__in=[ShareRequest.Status.CANCELLED, ShareRequest.Status.REJECTED]
            ).first()
            if req:
                return {
                    'id': req.id,
                    'quantity': str(req.quantity),
                    'status': req.status,
                    'created_at': req.created_at
                }
        return None

    def get_has_active_request(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.requests.filter(requester=request.user).exclude(
                status__in=[ShareRequest.Status.CANCELLED, ShareRequest.Status.REJECTED]
            ).exists()
        return False

    def get_requests(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.owner_id == request.user.id:
            reqs = obj.requests.all().order_by('-created_at')
            return ShareRequestSerializer(reqs, many=True, context=self.context).data
        return []


class FoodShareCreateSerializer(serializers.ModelSerializer):
    food_item_id = serializers.IntegerField(write_only=True)
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    unit = serializers.CharField(required=False, allow_blank=True, max_length=20)
    description = serializers.CharField(required=False, allow_blank=True)
    pickup_note = serializers.CharField(required=False, allow_blank=True)
    expires_at = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = FoodShare
        fields = [
            'food_item_id',
            'title',
            'description',
            'quantity',
            'unit',
            'visibility',
            'pickup_note',
            'expires_at'
        ]

    def validate_quantity(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Share quantity must be greater than zero.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        food_item_id = attrs.get('food_item_id')

        try:
            food_item = FoodItem.objects.get(id=food_item_id, user=user)
        except FoodItem.DoesNotExist:
            raise serializers.ValidationError({"food_item_id": "Invalid food item or unauthorized."})

        if food_item.quantity <= Decimal('0.00') or food_item.status == FoodItem.Status.CONSUMED:
            raise serializers.ValidationError({"food_item_id": "Cannot share consumed or zero-quantity food items."})

        if food_item.expiry_date < date.today():
            raise serializers.ValidationError({"food_item_id": "Cannot share expired food items."})

        # Calculate already allocated quantity for active shares on this food item
        allocated_agg = food_item.shares.filter(
            status__in=[FoodShare.Status.AVAILABLE, FoodShare.Status.PARTIALLY_CLAIMED]
        ).aggregate(tot=Sum('quantity'))
        allocated_qty = allocated_agg['tot'] or Decimal('0.00')

        unallocated = food_item.quantity - allocated_qty
        requested_share_qty = attrs.get('quantity')

        if requested_share_qty > unallocated:
            raise serializers.ValidationError({
                "quantity": f"Cannot share {requested_share_qty} {food_item.unit}. Only {unallocated} {food_item.unit} unallocated available."
            })

        attrs['food_item'] = food_item
        attrs['initial_quantity'] = requested_share_qty
        if not attrs.get('title'):
            attrs['title'] = food_item.name
        if not attrs.get('unit'):
            attrs['unit'] = food_item.unit
        if not attrs.get('expires_at'):
            attrs['expires_at'] = food_item.expiry_date

        return attrs


class ShareRequestSerializer(serializers.ModelSerializer):
    share_id = serializers.ReadOnlyField(source='share.id')
    share_title = serializers.ReadOnlyField(source='share.title')
    share_unit = serializers.ReadOnlyField(source='share.unit')
    share_owner_name = serializers.ReadOnlyField(source='share.owner.full_name')
    share_owner_flat = serializers.ReadOnlyField(source='share.owner.flat_number')
    requester = serializers.SerializerMethodField()
    requester_name = serializers.ReadOnlyField(source='requester.full_name')
    requester_flat = serializers.ReadOnlyField(source='requester.flat_number')
    requester_email = serializers.ReadOnlyField(source='requester.email')
    food_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = ShareRequest
        fields = [
            'id',
            'share',
            'share_id',
            'share_title',
            'share_unit',
            'share_owner_name',
            'share_owner_flat',
            'requester',
            'requester_name',
            'requester_flat',
            'requester_email',
            'food_photo_url',
            'quantity',
            'message',
            'status',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'share', 'requester', 'status', 'created_at', 'updated_at']

    def get_requester(self, obj):
        if obj.requester:
            return {
                'id': obj.requester.id,
                'full_name': obj.requester.full_name,
                'email': obj.requester.email,
                'flat_number': obj.requester.flat_number
            }
        return None

    def get_food_photo_url(self, obj):
        if obj.share and obj.share.food_item and obj.share.food_item.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.share.food_item.photo.url)
            return obj.share.food_item.photo.url
        return None


class ShareRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareRequest
        fields = ['quantity', 'message']

    def validate_quantity(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Request quantity must be greater than zero.")
        return value


class SavedShareSerializer(serializers.ModelSerializer):
    share_details = FoodShareSerializer(source='share', read_only=True)

    class Meta:
        model = SavedShare
        fields = ['id', 'user', 'share', 'share_details', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
