"""Exception handler producing the consistent SAMS error envelope."""
from collections import OrderedDict

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler


def _first_code(detail):
    """Extract the stable DRF error code from nested detail structures."""
    if hasattr(detail, "code"):
        return detail.code
    if isinstance(detail, dict):
        for value in detail.values():
            code = _first_code(value)
            if code:
                return code
    if isinstance(detail, (list, tuple)):
        for value in detail:
            code = _first_code(value)
            if code:
                return code
    return None


def _sams_code(exc) -> str:
    """Map exceptions to stable machine-readable codes."""
    code = _first_code(getattr(exc, "detail", None) if not isinstance(getattr(exc, "detail", None), (dict, list)) else getattr(exc, "detail", None))
    if isinstance(code, str) and code:
        base = code.upper()
        mapping = {
            "TOKEN_NOT_VALID": "TOKEN_INVALID",
            "NOT_AUTHENTICATED": "NOT_AUTHENTICATED",
            "PERMISSION_DENIED": "PERMISSION_DENIED",
            "NOT_FOUND": "NOT_FOUND",
            "METHOD_NOT_ALLOWED": "METHOD_NOT_ALLOWED",
            "THROTTLED": "THROTTLED",
            "VALIDATION_ERROR": "VALIDATION_ERROR",
            "PARSE_ERROR": "PARSE_ERROR",
            "UNSUPPORTED_MEDIA_TYPE": "UNSUPPORTED_MEDIA_TYPE",
            "DOES_NOT_EXIST": "NOT_FOUND",
            "INVALID": "VALIDATION_ERROR",
            "REQUIRED": "VALIDATION_ERROR",
            "BLANK": "VALIDATION_ERROR",
            "NULL": "VALIDATION_ERROR",
            "MAX_LENGTH": "VALIDATION_ERROR",
            "MIN_VALUE": "VALIDATION_ERROR",
            "MAX_VALUE": "VALIDATION_ERROR",
            "INVALID_CHOICE": "VALIDATION_ERROR",
            "UNIQUE": "VALIDATION_ERROR",
        }
        return mapping.get(base, base)
    return "ERROR"


def sams_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        if isinstance(exc, Http404):
            return _error_response("ไม่พบข้อมูลที่ต้องการ", "NOT_FOUND", 404)
        if isinstance(exc, DjangoPermissionDenied):
            return _error_response("คุณไม่มีสิทธิ์เข้าถึงส่วนนี้", "PERMISSION_DENIED", 403)
        # Unhandled — re-raise so Django logs it (no silent fake responses).
        return None

    if isinstance(exc, exceptions.Throttled):
        wait = getattr(exc, "wait", None)
        body = {
            "success": False,
            "message": "คำขอถึงขีดจำกัด กรุณารอสักครู่แล้วลองอีกครั้ง",
            "code": "THROTTLED",
        }
        if wait is not None:
            body["data"] = {"wait_seconds": int(wait)}
        response.data = body
        return response

    if isinstance(response.data, dict) and response.data.get("success") is False:
        return response

    if isinstance(response.data, dict):
        errors = response.data
        message = _first_message(errors)
    else:
        errors = {"detail": response.data}
        message = _stringify(response.data)

    http_status = response.status_code
    title = {
        400: "ข้อมูลที่ส่งมาไม่ถูกต้อง",
        401: "กรุณาเข้าสู่ระบบก่อนใช้งาน",
        403: "คุณไม่มีสิทธิ์เข้าถึงส่วนนี้",
        404: "ไม่พบข้อมูลที่ต้องการ",
        405: "วิธีการเรียกใช้งานไม่ถูกต้อง",
        409: "ข้อมูลขัดแย้งกัน",
        429: "คำขอถึงขีดจำกัด กรุณารอสักครู่",
        500: "เกิดข้อผิดพลาดภายในระบบ",
    }.get(http_status, "เกิดข้อผิดพลาด")

    response.data = OrderedDict(
        [
            ("success", False),
            ("message", title if http_status in (400, 401, 403, 404) else message),
            ("code", _sams_code(exc)),
            ("errors", errors if http_status == 400 else None),
        ]
    )
    return response


def _error_response(message: str, code: str, status: int):
    from rest_framework.response import Response

    return Response(
        {"success": False, "message": message, "code": code}, status=status
    )


def _first_message(errors) -> str:
    if isinstance(errors, dict):
        for value in errors.values():
            text = _stringify(value)
            if text:
                return text
        return ""
    return _stringify(errors)


def _stringify(value) -> str:
    if isinstance(value, (list, tuple)):
        return _stringify(value[0]) if value else ""
    if isinstance(value, dict):
        for v in value.values():
            text = _stringify(v)
            if text:
                return text
        return ""
    return str(getattr(value, "detail", value))
