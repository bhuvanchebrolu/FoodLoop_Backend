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
