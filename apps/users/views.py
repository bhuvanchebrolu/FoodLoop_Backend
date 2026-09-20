from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    RegisterSerializer, 
    LoginSerializer, 
    UserSerializer, 
    ProfileUpdateSerializer, 
    UserSettingsSerializer
)
from .models import UserSettings
from apps.common.utils import log_activity
from apps.common.permissions import IsOwnerOrAdmin, IsResident

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            user_data = UserSerializer(user).data
            
            # Log audit activity
            log_activity(
                user=user, 
                action='USER_REGISTERED', 
                entity_type='User', 
                entity_id=user.id,
                metadata={'email': user.email, 'role': user.role}
            )

            return Response({
                'message': 'Account created successfully!',
                'user': user_data,
                'tokens': tokens
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Registration failed. Please check your inputs.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)
            user_data = UserSerializer(user).data

            # Log audit activity
            log_activity(
                user=user, 
                action='USER_LOGGED_IN', 
                entity_type='User', 
                entity_id=user.id
            )

            return Response({
                'message': 'Logged in successfully!',
                'user': user_data,
                'tokens': tokens
            }, status=status.HTTP_200_OK)

        return Response({
            'message': 'Authentication failed.',
            'errors': serializer.errors
        }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        
        return Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsResident]

    def get(self, request):
        return get_profile_summary_response(request.user)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            user = serializer.save()
            
            # Log audit activity
            log_activity(
                user=user,
                action='PROFILE_UPDATED',
                entity_type='User',
                entity_id=user.id,
                metadata={'updated_fields': list(request.data.keys())}
            )

            return Response({
                'message': 'Profile updated successfully.',
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response({
            'message': 'Unable to update profile.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ProfileSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return get_profile_summary_response(request.user)


def get_profile_summary_response(user):
    from django.db.models import Sum
    from apps.foods.models import FoodItem, ConsumptionRecord, WasteRecord
    from apps.shares.models import FoodShare, ShareRequest

    items_added = FoodItem.objects.filter(user=user).count()
    consumed_agg = ConsumptionRecord.objects.filter(user=user).aggregate(total=Sum('quantity'))
    consumed_total = float(consumed_agg['total'] or 0.0)
    consumed_count = ConsumptionRecord.objects.filter(user=user).count()

    wasted_agg = WasteRecord.objects.filter(user=user).aggregate(total=Sum('quantity'))
    wasted_total = float(wasted_agg['total'] or 0.0)
    wasted_count = WasteRecord.objects.filter(user=user).count()

    shares_created = FoodShare.objects.filter(owner=user).count()
    shares_completed_qs = FoodShare.objects.filter(owner=user, status=FoodShare.Status.COMPLETED)
    shares_completed = shares_completed_qs.count()

    requests_made = ShareRequest.objects.filter(requester=user).count()
    requests_completed = ShareRequest.objects.filter(requester=user, status=ShareRequest.Status.COMPLETED).count()

    food_shared_kg = float(shares_completed_qs.aggregate(total=Sum('initial_quantity'))['total'] or 0.0)
    food_saved_kg = round(consumed_total + food_shared_kg, 2)
    diverted_waste_kg = round(food_shared_kg + (consumed_total * 0.8), 2)
    estimated_value_saved_inr = round(food_saved_kg * 150.0, 2)

    return Response({
        'user': UserSerializer(user).data,
        'stats': {
            'items_added': items_added,
            'consumed_count': consumed_count,
            'consumed_total_kg': round(consumed_total, 2),
            'wasted_count': wasted_count,
            'wasted_total_kg': round(wasted_total, 2),
            'shares_created': shares_created,
            'shares_completed': shares_completed,
            'requests_made': requests_made,
            'requests_completed': requests_completed,
        },
        'impact': {
            'food_saved_kg': food_saved_kg,
            'food_shared_kg': round(food_shared_kg, 2),
            'diverted_waste_kg': diverted_waste_kg,
            'estimated_value_saved_inr': estimated_value_saved_inr,
        }
    }, status=status.HTTP_200_OK)



class UserSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsResident]

    def get(self, request):
        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        serializer = UserSettingsSerializer(settings_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        serializer = UserSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            settings_obj = serializer.save()

            # Log audit activity
            log_activity(
                user=request.user,
                action='SETTINGS_UPDATED',
                entity_type='UserSettings',
                entity_id=settings_obj.id,
                metadata={'updated_fields': list(request.data.keys())}
            )

            return Response({
                'message': 'Settings updated successfully.',
                'settings': serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            'message': 'Unable to update settings.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
