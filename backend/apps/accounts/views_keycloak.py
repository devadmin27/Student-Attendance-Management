"""Keycloak OIDC entrypoints."""
from __future__ import annotations

from urllib.parse import urlencode

from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.views import View
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.auth_policy import AccountStatusBlocked, blocked_login_message
from apps.accounts.external_identity import ExternalIdentity
from apps.accounts.keycloak.config import get_keycloak_config, is_keycloak_configured
from apps.accounts.keycloak.errors import (
    KEYCLOAK_ACCOUNT_DISABLED,
    KEYCLOAK_ACCOUNT_STATUS_BLOCKED,
    KEYCLOAK_AUTO_LINK_AMBIGUOUS,
    KEYCLOAK_AUTO_LINK_EMAIL_NOT_VERIFIED,
    KEYCLOAK_CLAIMS_INVALID,
    KEYCLOAK_CODE_EXCHANGE_FAILED,
    KEYCLOAK_DISABLED,
    KEYCLOAK_IDENTITY_NOT_LINKED,
    KEYCLOAK_INVALID_NONCE,
    KEYCLOAK_INVALID_REQUEST,
    KEYCLOAK_INVALID_STATE,
    KEYCLOAK_LOGIN_CANCELLED,
    KEYCLOAK_NOT_IMPLEMENTED,
    KEYCLOAK_TOKEN_INVALID,
)
from apps.accounts.keycloak.oidc_client import OidcError, build_authorization_url, exchange_code_and_verify
from apps.accounts.keycloak.state_store import create_flow_state, pop_flow_state
from apps.accounts.keycloak.user_mapping import find_user_by_keycloak_identity
from apps.accounts.models import User
from apps.audit.models import log_audit
from apps.accounts.views_auth import _set_refresh_cookie, _blacklist
from common.exceptions import _error_response


class KeycloakConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cfg = get_keycloak_config()
        enabled = bool(cfg.enabled and is_keycloak_configured(cfg))
        return Response(
            {
                "success": True,
                "message": "OK",
                "data": {
                    "enabled": enabled,
                },
            }
        )


class KeycloakLoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cfg = get_keycloak_config()
        if not cfg.enabled or not is_keycloak_configured(cfg):
            return _error_response(
                "การเข้าสู่ระบบด้วย Keycloak ปิดใช้งานอยู่",
                KEYCLOAK_DISABLED,
                status.HTTP_400_BAD_REQUEST,
            )
        next_path = request.query_params.get("next") or None
        if next_path and not next_path.startswith("/"):
            next_path = None
        flow = create_flow_state(next_path)
        import base64
        import hashlib

        digest = hashlib.sha256(flow.code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        url = build_authorization_url(
            cfg, state=flow.state, nonce=flow.nonce, code_challenge=code_challenge
        )
        log_audit(
            actor=None,
            action="auth_keycloak_login_started",
            resource_type="auth",
            request=request,
            metadata={"provider": "keycloak"},
        )
        return HttpResponseRedirect(url)


class KeycloakCallbackView(View):
    def get(self, request):
        cfg = get_keycloak_config()
        frontend_base = cfg.frontend_base_url.rstrip("/") if cfg.frontend_base_url else ""
        callback_path = "/auth/callback"

        def redirect_error(code: str, next_path: str | None = None):
            if frontend_base:
                params = {"error": code}
                if next_path and next_path.startswith("/"):
                    params["next"] = next_path
                return HttpResponseRedirect(f"{frontend_base}{callback_path}?{urlencode(params)}")
            return _error_response(code, code, status.HTTP_400_BAD_REQUEST)

        if not cfg.enabled or not is_keycloak_configured(cfg):
            return redirect_error(KEYCLOAK_DISABLED)

        error = request.GET.get("error")
        if error:
            if error == "access_denied":
                log_audit(actor=None, action="auth_keycloak_login_failed", resource_type="auth", request=request, metadata={"code": KEYCLOAK_LOGIN_CANCELLED})
                return redirect_error(KEYCLOAK_LOGIN_CANCELLED)
            log_audit(actor=None, action="auth_keycloak_login_failed", resource_type="auth", request=request, metadata={"code": KEYCLOAK_INVALID_REQUEST, "idp_error": error})
            return redirect_error(KEYCLOAK_INVALID_REQUEST)

        state = request.GET.get("state") or ""
        stored = pop_flow_state(state)
        if not stored:
            log_audit(actor=None, action="auth_keycloak_login_failed", resource_type="auth", request=request, metadata={"code": KEYCLOAK_INVALID_STATE})
            return redirect_error(KEYCLOAK_INVALID_STATE)

        next_path = stored.get("next_path")
        code = request.GET.get("code") or ""
        if not code:
            log_audit(actor=None, action="auth_keycloak_login_failed", resource_type="auth", request=request, metadata={"code": KEYCLOAK_INVALID_REQUEST})
            return redirect_error(KEYCLOAK_INVALID_REQUEST)

        try:
            info = exchange_code_and_verify(
                cfg,
                code=code,
                code_verifier=stored["code_verifier"],
                expected_nonce=stored["nonce"],
            )
        except OidcError as exc:
            code_name = str(exc) if str(exc) in {
                KEYCLOAK_CODE_EXCHANGE_FAILED,
                KEYCLOAK_TOKEN_INVALID,
                KEYCLOAK_INVALID_NONCE,
                KEYCLOAK_CLAIMS_INVALID,
            } else KEYCLOAK_TOKEN_INVALID
            log_audit(actor=None, action="auth_keycloak_login_failed", resource_type="auth", request=request, metadata={"code": code_name})
            return redirect_error(code_name, next_path)
        except Exception:
            log_audit(actor=None, action="auth_keycloak_login_failed", resource_type="auth", request=request, metadata={"code": KEYCLOAK_TOKEN_INVALID})
            return redirect_error(KEYCLOAK_TOKEN_INVALID, next_path)

        user = find_user_by_keycloak_identity(info.issuer, info.sub)
        auto_linked = False
        link_method = None

        if user is None:
            if cfg.auto_link_by_verified_email:
                email_norm = (info.email or "").strip().lower()
                domain_ok = True
                if cfg.auto_link_allowed_domains:
                    if "@" not in email_norm:
                        domain_ok = False
                    else:
                        dom = email_norm.rsplit("@", 1)[-1]
                        domain_ok = dom in cfg.auto_link_allowed_domains

                if not info.email_verified:
                    log_audit(
                        actor=None,
                        action="auth_keycloak_login_failed",
                        resource_type="auth",
                        request=request,
                        metadata={"code": KEYCLOAK_AUTO_LINK_EMAIL_NOT_VERIFIED, "issuer": info.issuer},
                    )
                    return redirect_error(KEYCLOAK_IDENTITY_NOT_LINKED, next_path)
                if not email_norm or not domain_ok:
                    log_audit(
                        actor=None,
                        action="auth_keycloak_login_failed",
                        resource_type="auth",
                        request=request,
                        metadata={"code": KEYCLOAK_IDENTITY_NOT_LINKED, "issuer": info.issuer, "reason": "email_domain"},
                    )
                    return redirect_error(KEYCLOAK_IDENTITY_NOT_LINKED, next_path)

                matches = list(
                    User.objects.filter(email__iexact=email_norm, is_active=True).order_by("id")[:3]
                )
                if len(matches) != 1:
                    code = KEYCLOAK_AUTO_LINK_AMBIGUOUS if len(matches) > 1 else KEYCLOAK_IDENTITY_NOT_LINKED
                    log_audit(
                        actor=None,
                        action="auth_keycloak_login_failed",
                        resource_type="auth",
                        request=request,
                        metadata={"code": code, "issuer": info.issuer},
                    )
                    return redirect_error(code, next_path)

                matched_user = matches[0]
                msg = blocked_login_message(matched_user)
                if msg or not matched_user.is_active:
                    log_audit(
                        actor=matched_user,
                        action="auth_keycloak_login_failed",
                        resource_type="auth",
                        resource_id=str(matched_user.id),
                        request=request,
                        metadata={"code": KEYCLOAK_ACCOUNT_STATUS_BLOCKED},
                    )
                    return redirect_error(KEYCLOAK_ACCOUNT_STATUS_BLOCKED, next_path)

                try:
                    with transaction.atomic():
                        ei = (
                            ExternalIdentity.objects.select_for_update()
                            .filter(provider="keycloak", issuer=info.issuer, subject=info.sub)
                            .first()
                        )
                        if ei is not None:
                            ei_user = ei.user
                        else:
                            ei = ExternalIdentity.objects.create(
                                provider="keycloak",
                                issuer=info.issuer,
                                subject=info.sub,
                                user=matched_user,
                            )
                            ei_user = matched_user
                            auto_linked = True
                            link_method = "verified_email"
                        # refresh last_login_at if helper not used
                        from django.utils import timezone

                        ei.last_login_at = timezone.now()
                        ei.save(update_fields=["last_login_at"])
                    user = ei_user
                except IntegrityError:
                    log_audit(
                        actor=None,
                        action="auth_keycloak_login_failed",
                        resource_type="auth",
                        request=request,
                        metadata={"code": KEYCLOAK_IDENTITY_NOT_LINKED, "reason": "race_integrity"},
                    )
                    return redirect_error(KEYCLOAK_IDENTITY_NOT_LINKED, next_path)
            else:
                log_audit(
                    actor=None,
                    action="auth_keycloak_login_failed",
                    resource_type="auth",
                    request=request,
                    metadata={"code": KEYCLOAK_IDENTITY_NOT_LINKED},
                )
                return redirect_error(KEYCLOAK_IDENTITY_NOT_LINKED, next_path)

        if user is None:
            log_audit(
                actor=None,
                action="auth_keycloak_login_failed",
                resource_type="auth",
                request=request,
                metadata={"code": KEYCLOAK_IDENTITY_NOT_LINKED},
            )
            return redirect_error(KEYCLOAK_IDENTITY_NOT_LINKED, next_path)

        if not user.is_active:
            log_audit(actor=user, action="auth_keycloak_login_failed", resource_type="auth", resource_id=str(user.id), request=request, metadata={"code": KEYCLOAK_ACCOUNT_DISABLED})
            return redirect_error(KEYCLOAK_ACCOUNT_DISABLED, next_path)

        msg = blocked_login_message(user)
        if msg:
            log_audit(actor=user, action="auth_keycloak_login_failed", resource_type="auth", resource_id=str(user.id), request=request, metadata={"code": KEYCLOAK_ACCOUNT_STATUS_BLOCKED})
            return redirect_error(KEYCLOAK_ACCOUNT_STATUS_BLOCKED, next_path)

        refresh = RefreshToken.for_user(user)
        meta = {"provider": "keycloak", "issuer": info.issuer, "auto_linked": auto_linked}
        if link_method:
            meta["link_method"] = link_method
        log_audit(actor=user, action="auth_keycloak_login_success", resource_type="auth", resource_id=str(user.id), request=request, metadata=meta)

        if frontend_base:
            params = {"ok": "1"}
            if next_path and next_path.startswith("/"):
                params["next"] = next_path
            resp = HttpResponseRedirect(f"{frontend_base}{callback_path}?{urlencode(params)}")
        else:
            resp = HttpResponseRedirect(f"{callback_path}?ok=1")
        _set_refresh_cookie(resp, str(refresh))
        return resp


class AuthMethodView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cfg = get_keycloak_config()
        enabled = bool(cfg.enabled and is_keycloak_configured(cfg))
        return Response(
            {
                "success": True,
                "message": "OK",
                "data": {
                    "keycloak_enabled": enabled,
                    "default_method": "keycloak" if enabled else "local",
                },
            }
        )


class KeycloakLogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.conf import settings as dj_settings

        cfg = get_keycloak_config()
        cookie_name = getattr(dj_settings, "REFRESH_COOKIE_NAME", "sams_refresh")
        cookie_token = request.COOKIES.get(cookie_name)
        body_token = request.data.get("refresh") if hasattr(request, "data") else None
        value = body_token or cookie_token
        if value:
            try:
                token = RefreshToken(value)
                _blacklist(token)
            except Exception:
                pass
        resp = Response(
            {
                "success": True,
                "message": "ออกจากระบบสำเร็จ",
                "data": {
                    "keycloak_end_session_url": None,
                },
            }
        )
        from apps.accounts.views_auth import _clear_refresh_cookie

        _clear_refresh_cookie(resp)
        if cfg.enabled and cfg.end_session_on_logout and cfg.base_url and cfg.realm:
            params = {}
            if cfg.post_logout_redirect_uri:
                params["post_logout_redirect_uri"] = cfg.post_logout_redirect_uri
                params["client_id"] = cfg.client_id
            end_url = f"{cfg.base_url}/realms/{cfg.realm}/protocol/openid-connect/logout"
            if params:
                end_url = f"{end_url}?{urlencode(params)}"
            resp.data["data"]["keycloak_end_session_url"] = end_url
        log_audit(
            actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
            action="auth_keycloak_logout",
            resource_type="auth",
            request=request,
        )
        return resp
