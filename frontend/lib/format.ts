/** Thai date/time formatting helpers (Asia/Bangkok, DD/MM/YYYY, 24-hour). */

export const BANGKOK_TIMEZONE = "Asia/Bangkok";

export function formatThaiDate(input: string | Date | null | undefined): string {
  if (!input) return "-";
  const date = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("th-TH-u-ca-gregory-nu-latn", {
    timeZone: BANGKOK_TIMEZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function formatThaiTime(input: string | Date | null | undefined): string {
  if (!input) return "-";
  const date = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: BANGKOK_TIMEZONE,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatThaiDateTime(
  input: string | Date | null | undefined,
): string {
  if (!input) return "-";
  return `${formatThaiDate(input)} ${formatThaiTime(input)}`;
}
