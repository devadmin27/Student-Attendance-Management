"""Fix dev DB edit_reason (was mangled to '?' sent by ANSI console client) and
PROVE the backend stores proper Thai when the body is real UTF-8 (as axios does)."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
RECORD = "8efc0655-9137-4624-b03d-f52b0b6273cc"
REASON = "ยื่นใบลาป่วยล่วงหน้า — อนุมัติเป็นลากิจ (ยืนยัน? โชว์ \"อักขระไทย\" ครบ)"


def http(method, url, token=None, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + url, method=method, data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


status, login = http("POST", "/auth/login/", body={"username": "instructor1", "password": "SamsDev!2026"})
token = login["data"]["access"]

status, patched = http(
    "PATCH", f"/attendance/records/{RECORD}/",
    token, {"status": "excused", "edit_reason": REASON},
)
print("patch:", status)
reason = patched["data"]["edit_reason"]
print("stored reason:", reason)
print("intact (no '?'):", "?" not in reason, "| equals source:", reason == REASON)
