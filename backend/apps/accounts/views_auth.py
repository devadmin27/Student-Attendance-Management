"""Auth endpoints: login, refresh, logout, me. Spec §4, §13.1."""
from django.conf import settings
from rest_framework import generics, serializers, status, views
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.serializers import MeSerializer, SAMSLoginSerializer
from apps.audit.models import log_audit
from apps.audit.throttles import LoginRateThrottle
from common.exceptions import _error_response
from common.responses import success_response


class RefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False)


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False)


class RefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class LogoutResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()


def _set_refresh_cookie(response, refresh_token: str) -> None:
    """Store the refresh token in an HttpOnly cookie instead of localStorage."""
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path="/api/v1/auth/",
    )


def _clear_refresh_cookie(response) -> None:
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth/")


class LoginView(TokenObtainPairView):
    serializer_class = SAMSLoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        refresh = data.pop("refresh")
        response = Response(
            {"success": True, "message": "เข้าสู่ระบบสำเร็จ", "data": data},
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, refresh)
        log_audit(
            actor=serializer.user,
            action="auth_login_success",
            resource_type="auth",
            resource_id=data.get("user", {}).get("id", ""),
            request=request,
        )
        return response


class RefreshView(views.APIView):
    """Rotate refresh token; supports cookie or body token.

    Blacklist-after-rotation (settings) makes a previously used refresh token
    unusable — token reuse is rejected with 401 and audited.
    """

    permission_classes = [AllowAny]
    throttle_scope = "login"

    @extend_schema(request=RefreshRequestSerializer, responses=RefreshResponseSerializer)
    def post(self, request):
        body_token = request.data.get("refresh") if hasattr(request, "data") else None
        cookie_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        token_value = body_token or cookie_token
        if not token_value:
            return _error_response(
                "ไม่พบ Refresh Token กรุณาเข้าสู่ระบบใหม่", "REFRESH_MISSING", 401
            )
        try:
            old = RefreshToken(token_value)
        except Exception:
            return _error_response("เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่", "REFRESH_INVALID", 401)
        try:
            old.check_blacklist()
        except Exception:
            # Reuse of a rotated token — audited defensively.
            log_audit(
                actor=None, action="auth_refresh_reuse_blocked", resource_type="auth",
                request=request,
            )
            response = _error_response(
                "เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่", "REFRESH_REUSE", 401
            )
            _clear_refresh_cookie(response)
            return response

        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.settings import api_settings as jwt_settings

        try:
            user = get_user_model().objects.get(id=old.payload[jwt_settings.USER_ID_CLAIM])
        except (KeyError, get_user_model().DoesNotExist):
            return _error_response("เซสชันไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่", "REFRESH_INVALID", 401)
        if not (user.is_active and user.role):
            return _error_response("บัญชีถูกระงับการใช้งาน", "ACCOUNT_SUSPENDED", 403)

        _blacklist(old)
        new = RefreshToken.for_user(user)
        response = Response(
            {
                "success": True,
                "message": "ต่ออายุเซสชันสำเร็จ",
                "data": {
                    "access": str(new.access_token),
                    "user": {
                        "id": str(user.id),
                        "username": user.username,
                        "role": user.role,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, str(new))
        return response


def _blacklist(token: RefreshToken) -> None:
    try:
        token.blacklist()
    except Exception:
        pass


class LogoutView(views.APIView):
    """Revoke the presented refresh token (cookie-first, then body)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutRequestSerializer, responses=LogoutResponseSerializer)
    def post(self, request):
        cookie_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        body_token = request.data.get("refresh") if hasattr(request, "data") else None
        value = body_token or cookie_token
        if value:
            try:
                token = RefreshToken(value)
                _blacklist(token)
            except Exception:
                pass  # Logout should always succeed idempotently
        response = success_response(message="ออกจากระบบสำเร็จ")
        _clear_refresh_cookie(response)
        log_audit(
            actor=request.user, action="auth_logout", resource_type="auth",
            resource_id=str(request.user.id), request=request,
        )
        return response


class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
