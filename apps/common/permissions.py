from rest_framework import permissions

class IsResident(permissions.BasePermission):
    """
    Permission check to allow users with RESIDENT role (or ADMINs who have full access).
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in ['RESIDENT', 'ADMIN'])
        )

class IsAdmin(permissions.BasePermission):
    """
    Permission check to restrict access strictly to users with ADMIN role.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role == 'ADMIN' or request.user.is_staff or request.user.is_superuser)
        )

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission check to ensure a user can only access or modify their own object unless they are an admin.
    """
    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == 'ADMIN' or request.user.is_staff or request.user.is_superuser:
            return True
        # Check if the object belongs to the requesting user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user
