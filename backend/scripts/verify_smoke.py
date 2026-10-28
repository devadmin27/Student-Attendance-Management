"""Byte-accurate verification of Thai text in API responses + 409 duplicate body."""
import io
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def http(method, url, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + url, method=method, data=data,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


# 1) login
status, login = http("POST", "/auth/login/", body={"username": "instructor1", "password": "SamsDev!2026"})
token = login["data"]["access"]
print("login:", status, "user.role =", login["data"]["user"]["role"])

# 2) records list — Thai student_name must be correct UTF-8 in actual bytes
status, recs = http("GET", "/attendance/records/?attendance_session=65de7cae-4839-4fb1-bfdd-a23e0f37de5b&page_size=1", token)
row = recs["data"][0]
print("edit_reason repr:", repr(row["edit_reason"]))
print("record status:", row["status"])
print("student_name repr:", repr(row["student_name"])[:90])

# 3) 409 duplicate check-in — read code field from actual error envelope
status, slogin = http("POST", "/auth/login/", body={"username": "student03", "password": "SamsDev!2026"})
stoken = slogin["data"]["access"]
# get current valid QR token raw: re-issue as instructor (admin can't? instructor can) — use roster instead.
st, qr = http("POST", "/attendance/sessions/65de7cae-4839-4fb1-bfdd-a23e0f37de5b/qr-token/", token)
raw_token = qr["data"]["qr"]
st, dup = http("POST", "/attendance/check-in/", stoken, {"token": raw_token})
print("dup check-in:", st, "| envelope:", json.dumps(dup, ensure_ascii=True)[:300])
st, ok = http("POST", "/attendance/check-in/", stoken, {"token": raw_token})
print("second dup:", st)

# 4) audit — envelope shape check (pagination sibling)
st, audit = http("GET", "/audit-logs/?page_size=3", token)
print("audit keys:", sorted(audit.keys()))
print("audit count:", audit["pagination"]["count"] if "pagination" in audit else "NO pagination")
print("latest action:", audit["data"][0].get("action"), "| detail:", repr(audit["data"][0].get("detail"))[:80])
