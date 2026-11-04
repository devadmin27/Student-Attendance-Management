"""Scoped throttles (spec §16: excessive API requests)."""
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class UserScopeThrottle(SimpleRateThrottle):
    """Rate throttle keyed by authenticated user for one fixed scope.

    Unlike ScopedRateThrottle this reads its own ``scope`` from the class,
    so a single view can apply two independent buckets (e.g. hourly + burst)
    without the view's ``throttle_scope`` overriding them.
    """

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class LoginRateThrottle(ScopedRateThrottle):
    throttle_scope = "login"


class CheckInThrottle(ScopedRateThrottle):
    throttle_scope = "checkin"


class CSVImportThrottle(ScopedRateThrottle):
    throttle_scope = "csv_import"


class AttendancePollThrottle(UserScopeThrottle):
    """Sustained roster-polling budget (per instructor, per hour)."""

    scope = "attendance_poll"


class AttendancePollBurstThrottle(UserScopeThrottle):
    """Short burst guard for roster polling (per instructor, per minute)."""

    scope = "attendance_poll_burst"
