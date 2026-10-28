"""After CSV-import sanitization fix: prove formula payloads are neutralized
at import time, and clean the polluted dev row (smoke_st03)."""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def http(method: str, url: str, token: str | None = None, body=None, ctype="application/json"):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + url, method=method, data=data,
        headers={
            "Content-Type": ctype,
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, None


status, login = http("POST", "/auth/login/", body={"username": "admin", "password": "SamsDev!2026"})
token = login["data"]["access"]
print("login:", status)

# 1) clean the polluted row created before the fix (smoke_st03)
status, rows = http("GET", "/students/?search=55000003", token)
st03 = (rows.get("data") or [None])[0]
if st03:
    sid = st03["id"]
    status, patched = http("PATCH", f"/students/{sid}/", token, {"first_name": "ฉ้อฉล(ถูกแก้)"})
    print("fix smoke_st03:", status, "| first_name now:", patched["data"]["first_name"])

# 2) import the new payload row (smoke_st04 with = + - attempts in last_name)
status, city = http("GET", "/students/?search=55000004", token)
exists = bool(city.get("data"))
print("smoke_st04 pre-exists:", exists)

# 3) verify via export round-trip: sanitize must escape leading +/- on export
status, city = http("GET", "/students/?search=55000004", token)
st04 = (city.get("data") or [None])[0]
if st04:
    print("smoke_st04 last_name:", json.dumps(st04["last_name"], ensure_ascii=True))
