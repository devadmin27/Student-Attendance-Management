"""Shared rule for which student profiles may use the authenticated API."""
from rest_framework.exceptions import APIException

# Leave of absence is still an enrolled student — only final states block
# access. User.is_active stays an independent account-level flag.
BLOCKED_STATUSES = {"graduated", "withdrawn"}

BLOCKED_MESSAGES = {
    "graduated": "คุณสำเร็จการศึกษาแล้ว จึงไม่สามารถเข้าสู่ระบบได้",
    "withdrawn": "คุณลาออกแล้ว จึงไม่สามารถเข้าสู่ระบบได้",
}


class AccountStatusBlocked(APIException):
    status_code = 403
    default_detail = "บัญชีนี้ไม่สามารถเข้าสู่ระบบได้"
    default_code = "ACCOUNT_STATUS_BLOCKED"


def blocked_login_message(user):
    """Return a Thai reason when the user's student status blocks sign-in."""
    profile = getattr(user, "student_profile", None)
    if profile is None or profile.status not in BLOCKED_STATUSES:
        return None
    return BLOCKED_MESSAGES[profile.status]
