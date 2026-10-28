"""Response envelope renderer (SAMS envelope).

DRF default `list` responses already carry the SAMS envelope through
`common.pagination.StandardPagination`, but single-object responses from
plain ModelViewSet actions (retrieve/patch options etc., plus any custom
view that forgets `success_response`) are bare payloads. The frontend
client contract is `{success, message, data[, pagination]}`; this renderer
wraps every 2xx bare payload once. Responses that already carry the
envelope (success_response / StandardPagination / error envelopes) pass
through untouched, so no double wrapping occurs.
"""
import json

from rest_framework.renderers import JSONRenderer


class SamsJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        raw = super().render(data, accepted_media_type, renderer_context)
        if response is None or response.status_code >= 400:
            return raw  # errors already enveloped by the exception handler
        request = renderer_context.get("request")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return raw  # non-JSON payload (CSV etc.) — never touched
        if isinstance(parsed, dict) and "success" in parsed:
            return raw  # already enveloped (success/pagination/error)
        is_get = (getattr(request, "method", "") or "").upper() == "GET"
        message = "โหลดข้อมูลสำเร็จ" if is_get else "ดำเนินการสำเร็จ"
        wrapped = json.dumps(
            {"success": True, "message": message, "data": parsed},
            ensure_ascii=False,
        )
        return wrapped.encode("utf-8")
