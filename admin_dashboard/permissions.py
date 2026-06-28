from rest_framework.permissions import BasePermission

class IsOwner(BasePermission):
    """
    Allows access only to authenticated users with role = 'owner'.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'owner'
        )
