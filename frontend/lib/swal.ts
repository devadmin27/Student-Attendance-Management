/**
 * SweetAlert2 helpers used across SAMS pages.
 * Toasts for feedback; themed dialogs (never blocking error stack traces).
 */
import Swal from "sweetalert2";

export async function toastSuccess(title: string): Promise<void> {
  await Swal.fire({
    toast: true,
    position: "top-end",
    icon: "success",
    title,
    showConfirmButton: false,
    timer: 2200,
    timerProgressBar: true,
  });
}

export async function toastInfo(title: string): Promise<void> {
  await Swal.fire({
    toast: true,
    position: "top-end",
    icon: "info",
    title,
    showConfirmButton: false,
    timer: 2600,
    timerProgressBar: true,
  });
}

export async function alertError(message: string, text?: string): Promise<void> {
  await Swal.fire({
    icon: "error",
    title: message,
    text,
    confirmButtonColor: "#1d4ed8",
    confirmButtonText: "ตกลง",
  });
}

export async function confirmDialog(options: {
  title: string;
  text?: string;
  confirmText?: string;
  icon?: "warning" | "question";
}): Promise<boolean> {
  const result = await Swal.fire({
    title: options.title,
    text: options.text,
    icon: options.icon ?? "warning",
    showCancelButton: true,
    confirmButtonColor: "#1d4ed8",
    cancelButtonColor: "#64748b",
    confirmButtonText: options.confirmText ?? "ยืนยัน",
    cancelButtonText: "ยกเลิก",
    reverseButtons: true,
  });
  return result.isConfirmed;
}

/** Escape untrusted API strings before putting them in a SweetAlert `html` body. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Batch summary dialog: counts plus an optional per-row list so the user can
 * see exactly which rows were skipped or rejected.
 */
export async function showBatchSummary(options: {
  icon: "success" | "warning" | "error";
  title: string;
  summary: string;
  details?: string[];
}): Promise<void> {
  const details =
    options.details && options.details.length > 0
      ? `<div style="margin-top:12px;max-height:220px;overflow-y:auto;text-align:left;font-size:13px;line-height:1.6">${options.details
          .map((line) => `<div>• ${escapeHtml(line)}</div>`)
          .join("")}</div>`
      : "";
  await Swal.fire({
    icon: options.icon,
    title: options.title,
    html: `<div>${escapeHtml(options.summary)}</div>${details}`,
    confirmButtonColor: "#1d4ed8",
    confirmButtonText: "ตกลง",
  });
}

export async function promptReason(title: string, text?: string): Promise<string | null> {
  const result = await Swal.fire<string>({
    title,
    text,
    input: "textarea",
    inputPlaceholder: "ระบุเหตุผลการแก้ไข",
    showCancelButton: true,
    confirmButtonColor: "#1d4ed8",
    cancelButtonColor: "#64748b",
    confirmButtonText: "บันทึก",
    cancelButtonText: "ยกเลิก",
    inputValidator: (value) => {
      if (!value || value.trim().length === 0) {
        return "กรุณาระบุเหตุผล";
      }
      return null;
    },
  });
  if (!result.isConfirmed || !result.value) return null;
  return result.value.trim();
}
