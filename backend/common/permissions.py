"""Role-Based Access Control permission classes (SAMS spec §4.2).

All permission decisions are made from the authenticated Django User —
never from client-provided role claims.
"""
from rest_framework.permissions import BasePermission


def has_role(user, *roles: str) -> bool:
    return bool(user and user.is_authenticated and user.role in roles)


class RoleRequired(BasePermission):
    """Class-based declaration: allowed_roles = {"admin"}."""

    allowed_roles: set[str] = set()
    message = "คุณไม่มีสิทธิ์เข้าถึงส่วนนี้"

    def has_permission(self, request, view):
        roles = getattr(view, "allowed_roles", self.allowed_roles)
        if not roles:
            return True
        return has_role(request.user, *roles)


class IsAdmin(RoleRequired):
    allowed_roles = {"admin"}


class IsInstructor(RoleRequired):
    allowed_roles = {"instructor"}


class IsStudent(RoleRequired):
    allowed_roles = {"student"}


class IsAdminOrInstructor(RoleRequired):
    allowed_roles = {"admin", "instructor"}


class IsOwnerOrAdmin(BasePermission):
    """Object-level: students may only access their own data (IDOR guard)."""

    message = "คุณไม่มีสิทธิ์เข้าถึงข้อมูลของผู้อื่น"

    def has_object_permission(self, request, view, obj):
        if has_role(request.user, "admin"):
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "student", None)
        return owner is not None and owner == request.user
