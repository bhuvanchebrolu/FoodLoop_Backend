from rest_framework import serializers
from .models import Report
from apps.users.serializers import UserSerializer
from apps.shares.models import FoodShare
from apps.users.models import CustomUser

class ReportSerializer(serializers.ModelSerializer):
    reporter = UserSerializer(read_only=True)
    reviewed_by = UserSerializer(read_only=True)
    target_summary = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id',
            'reporter',
            'target_type',
            'target_id',
            'target_summary',
            'reason',
            'description',
            'status',
            'reviewed_by',
            'resolution_note',
            'created_at',
            'updated_at',
            'resolved_at'
        ]
        read_only_fields = [
            'id', 'reporter', 'status', 'reviewed_by', 
            'resolution_note', 'created_at', 'updated_at', 'resolved_at'
        ]

    def get_target_summary(self, obj):
        try:
            if obj.target_type == Report.TargetType.FOOD_SHARE:
                share = FoodShare.objects.select_related('owner').get(id=int(obj.target_id))
                return {
                    'title': share.title,
                    'owner_name': share.owner.full_name,
                    'owner_email': share.owner.email,
                    'status': share.status,
                    'quantity': f"{share.quantity} {share.unit}"
                }
            elif obj.target_type == Report.TargetType.USER:
                user = CustomUser.objects.get(id=int(obj.target_id))
                return {
                    'name': user.full_name,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active
                }
        except Exception:
            pass
        return {'id': obj.target_id, 'info': 'Target object unavailable or deleted'}


class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['target_type', 'target_id', 'reason', 'description']

    def validate(self, attrs):
        target_type = attrs.get('target_type')
        target_id = attrs.get('target_id')
        request = self.context.get('request')

        # Check target existence
        if target_type == Report.TargetType.FOOD_SHARE:
            if not FoodShare.objects.filter(id=target_id).exists():
                raise serializers.ValidationError({'target_id': 'Target food share does not exist.'})
        elif target_type == Report.TargetType.USER:
            if not CustomUser.objects.filter(id=target_id).exists():
                raise serializers.ValidationError({'target_id': 'Target user does not exist.'})

        # Prevent duplicate pending reports from same reporter on same target
        if request and request.user and request.user.is_authenticated:
            existing = Report.objects.filter(
                reporter=request.user,
                target_type=target_type,
                target_id=target_id,
                status__in=[Report.Status.PENDING, Report.Status.UNDER_REVIEW]
            ).exists()
            if existing:
                raise serializers.ValidationError({
                    'non_field_errors': 'You already have an active unresolved report pending for this item.'
                })

        return attrs


class ReportResolveSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=['DISMISS', 'CANCEL_SHARE', 'DEACTIVATE_USER', 'WARN_USER', 'NONE'],
        default='NONE'
    )
    resolution_note = serializers.CharField(required=False, allow_blank=True, default='')
