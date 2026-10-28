"""Small shared utilities."""
import csv
import io


def sanitize_csv_value(value) -> str:
    """Prevent CSV formula injection on export (spec §16).

    Values starting with =, +, -, @ are prefixed with a single quote so
    spreadsheet applications treat them as text.
    """
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def rows_to_csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    """Serialize rows to UTF-8-with-BOM CSV so Excel opens Thai text correct."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([sanitize_csv_value(v) for v in row])
    return buffer.getvalue().encode("utf-8-sig")
