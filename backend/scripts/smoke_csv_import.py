"""SAMS CSV student import smoke test — real UTF-8 Thai names, multipart upload.

Covers: import success rows, formula-injection sanitization (leading = / + / - ),
duplicate import rejection, and audit log entry afterwards.
"""
import io
import json
import pathlib
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
CSV = (
    "username,student_code,first_name,last_name,password,email,academic_year_level\n"
    "smoke_st01,55000001,สมชาย,ใจดีทั้งหมด,Smoke#2026,somchai.d@dev.ac.th,3\n"
    "smoke_st02,55000002,ประไหม,รักการเรียนรู้,Smoke#2026,,3\n"
    "smoke_st04,55000004,สะอาด,+HYPERLINK(\"http://evil\")ท้าย,Smoke#2026,,3\n"  # formula injection attempt — must be sanitized
)


def http(method: str, url: str, token: str | None = None, body=None, ctype="application/json"):
    data = body if isinstance(body, (bytes, bytearray)) else (
        json.dumps(body).encode("utf-8") if body is not None else None
    )
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

boundary = "----SamsSmokeX"
part = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="file"; filename="students.csv"\r\n'
    "Content-Type: text/csv\r\n\r\n"
).encode("utf-8") + CSV.encode("utf-8") + f"\r\n--{boundary}--\r\n".encode()

status, result = http(
    "POST", "/users/import-students/", token, part,
    ctype=f'multipart/form-data; boundary="{boundary}"',
)
print("import:", status)
if result:
    data = result.get("data", {})
    print("summary keys:", sorted(data.keys()) if isinstance(data, dict) else type(data))
    print(json.dumps(result, ensure_ascii=True)[:600])

# Second import → duplicates must be reported/rejected
status, again = http(
    "POST", "/users/import-students/", token, part,
    ctype=f'multipart/form-data; boundary="{boundary}"',
)
print("re-import:", status, "| success:", (again or {}).get("success"), "|", json.dumps((again or {}).get("data", {}), ensure_ascii=True)[:300])

# verify the login of an imported student works (proves password hashing on import)
status, ils = http("POST", "/auth/login/", body={"username": "smoke_st01", "password": "Smoke#2026"})
print("imported student login:", status, "| role:", (ils.get("data", {}).get("user", {}) or {}).get("role"))

# audit trail of the import
status, audit = http("GET", "/audit-logs/?page_size=5", token)
print("audit latest actions:", [row.get("action") for row in audit.get("data", [])][:5])
