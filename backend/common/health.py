"""Health check endpoint (spec §15, §18). Verifies DB connection."""
from django.db import connection
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.serializers import Serializer, CharField
from rest_framework.views import APIView
from rest_framework.response import Response

from config import settings


class HealthSerializer(Serializer):
    service = CharField()
    version = CharField()
    database = CharField()


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=HealthSerializer, summary="Health Check — ตรวจสถานะ API และ Database")
    def get(self, request):
        detail = {
            "service": "sams-api",
            "version": settings.PROJECT_VERSION,
            "database": "unknown",
        }
        healthy = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            detail["database"] = "connected"
        except OperationalError:
            detail["database"] = "unreachable"
            healthy = False
        http_status = 200 if healthy else 503
        return Response(
            {
                "success": healthy,
                "message": "ระบบทำงานปกติ" if healthy else "เชื่อมต่อฐานข้อมูลไม่ได้",
                "data": detail,
            },
            status=http_status,
        )
