"""Scoped throttles (spec §16: excessive API requests)."""
from rest_framework.throttling import ScopedRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    throttle_scope = "login"


class CheckInThrottle(ScopedRateThrottle):
    throttle_scope = "checkin"


class CSVImportThrottle(ScopedRateThrottle):
    throttle_scope = "csv_import"
