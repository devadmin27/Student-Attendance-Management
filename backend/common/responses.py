"""Consistent API response envelope helpers (SAMS spec §13.2)."""
from rest_framework import status


def success_response(data=None, message: str = "สำเร็จ", http_status: int = status.HTTP_200_OK):
    """Build a standard success payload without rendering immediately."""
    from rest_framework.response import Response

    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=http_status)


def error_response(message: str, code: str, http_status: int, errors=None):
    """Build a standard error payload."""
    from rest_framework.response import Response

    body = {"success": False, "message": message, "code": code}
    if errors is not None:
        body["errors"] = errors
    return Response(body, status=http_status)
