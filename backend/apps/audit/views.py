"""Audit logs: read-only for admins (no API edits/deletes; spec §16)."""
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import JSONParser

from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_username", "action", "resource_type",
            "resource_id", "metadata", "ip_address", "user_agent", "created_at",
        ]
        read_only_fields = fields
from common.permissions import IsAdmin


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor")
    permission_classes = [IsAdmin]
    filterset_fields = {"actor": ["exact"], "action": ["exact"], "resource_type": ["exact"]}
    search_fields = ["resource_id", "action"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    serializer_class = AuditLogSerializer
