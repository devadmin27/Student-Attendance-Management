"use client";
/**
 * Attachment list for a leave request (Phase 4).
 *
 * Files are private: every download goes through the authenticated API with
 * the role-scoped backend check, never a public media URL.
 */
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { alertError } from "@/lib/swal";
import type { LeaveAttachment } from "@/lib/types";

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function downloadAttachment(attachment: LeaveAttachment): Promise<void> {
  const response = await api.request<Blob>({
    url: attachment.download_url,
    method: "GET",
    responseType: "blob",
  });
  const objectUrl = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = attachment.original_name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

export default function LeaveAttachmentList({
  attachments,
  canDelete = false,
  onDelete,
  deletingId = null,
  emptyText = "ไม่มีไฟล์แนบ",
}: {
  attachments: LeaveAttachment[];
  canDelete?: boolean;
  onDelete?: (attachment: LeaveAttachment) => void;
  deletingId?: string | null;
  emptyText?: string;
}) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownload = async (attachment: LeaveAttachment) => {
    setDownloadingId(attachment.id);
    try {
      await downloadAttachment(attachment);
    } catch (error) {
      await alertError(
        "ดาวน์โหลดไฟล์แนบไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setDownloadingId(null);
    }
  };

  if (attachments.length === 0) {
    return <p className="mt-2 text-xs text-slate-500">{emptyText}</p>;
  }

  return (
    <ul className="mt-2 space-y-2">
      {attachments.map((attachment) => (
        <li
          key={attachment.id}
          className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
        >
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-slate-800">
              {attachment.original_name}
            </div>
            <div className="mt-0.5 text-xs text-slate-500">
              {attachment.attachment_type_display} ·{" "}
              {formatFileSize(attachment.size)}
              {attachment.uploaded_by_name
                ? ` · ผู้อัปโหลด ${attachment.uploaded_by_name}`
                : ""}
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleDownload(attachment)}
            disabled={downloadingId === attachment.id}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            {downloadingId === attachment.id ? "กำลังดาวน์โหลด…" : "ดาวน์โหลด"}
          </button>
          {canDelete && onDelete && (
            <button
              type="button"
              onClick={() => onDelete(attachment)}
              disabled={deletingId === attachment.id}
              className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              {deletingId === attachment.id ? "กำลังลบ…" : "ลบ"}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
