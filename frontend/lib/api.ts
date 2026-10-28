/**
 * SAMS API client.
 *
 * Access token lives in memory only (never localStorage). The refresh token
 * is an HttpOnly cookie owned by Django; Axios sends/receives it via
 * withCredentials. On 401 the client transparently refreshes once and
 * retries, matching spec §14.1.
 */
import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// ---- In-memory access token (SSOT is the AuthProvider access token) ----
let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// ---- Response envelope types (typed API responses) ----
export interface SamsEnvelope<T> {
  success: boolean;
  message: string;
  code?: string;
  data?: T;
  errors?: unknown;
  pagination?: {
    count: number;
    pages: number;
    current: number;
    next: string | null;
    previous: string | null;
    page_size: number;
  };
}

export type SamsResponse<T> = { data: T; envelope: SamsEnvelope<T> };

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

// ---- Auto-refresh logic ----
let refreshingPromise: Promise<boolean> | null = null;

/** Single-flight refresh — all code paths (interceptor + AuthProvider hydration)
 * share this promise so there is never a concurrent double rotation of the
 * refresh cookie (rotation + blacklist makes that fatal: last-write-wins cookie). */
export async function refreshSession(): Promise<boolean> {
  if (!refreshingPromise) {
    refreshingPromise = axios
      .post<SamsEnvelope<{ access: string }>>(
        `${API_BASE_URL}/auth/refresh/`,
        {},
        { withCredentials: true },
      )
      .then((response) => {
        if (response.data?.success && response.data.data?.access) {
          setAccessToken(response.data.data.access);
          return true;
        }
        return false;
      })
      .catch(() => false)
      .finally(() => {
        refreshingPromise = null;
      });
  }
  return refreshingPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<SamsEnvelope<unknown>>) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;
    const status = error.response?.status;
    const url = originalRequest?.url ?? "";

    const isAuthCall =
      url.includes("/auth/login/") ||
      url.includes("/auth/refresh/") ||
      url.includes("/auth/logout/");

    if (status === 401 && originalRequest && !originalRequest._retried && !isAuthCall) {
      originalRequest._retried = true;
      const refreshed = await refreshSession();
      if (refreshed) {
        return api.request(originalRequest);
      }
      setAccessToken(null);
      onSessionExpired?.();
    }
    const detail = error.response?.data;
    const message =
      detail?.message ??
      (status === 429 ? "คำขอถึงขีดจำกัด กรุณารอสักครู่" : "เกิดข้อผิดพลาดในการเชื่อมต่อระบบ");
    const code = detail?.code ?? "NETWORK_ERROR";
    const summary = summarizeValidationErrors(detail?.errors);

    return Promise.reject(
      new ApiError(summary ? `${message} — ${summary}` : message, code, status ?? 500),
    );
  },
);

/** Typed wrapper returning payload + envelope. */
// ---- In-memory helper: summarize field-level validation errors ----
function summarizeValidationErrors(errors: unknown): string {
  if (!errors || typeof errors !== "object") return typeof errors === "string" ? errors : "";
  const parts: string[] = [];
  for (const [field, messages] of Object.entries(errors as Record<string, unknown>)) {
    const list = Array.isArray(messages) ? messages : [messages];
    parts.push(`${field}: ${list.join(", ")}`);
  }
  return parts.join("; ");
}

export async function samsRequest<T>(
  config: Parameters<AxiosInstance["request"]>[0],
): Promise<SamsResponse<T>> {
  const response = await api.request<SamsEnvelope<T>>(config);
  // 204 (and any empty-body success) has no envelope — treat as success.
  if (response.data && typeof response.data === "object" && "success" in response.data) {
    if (!response.data.success) {
      const detail = summarizeValidationErrors(response.data.errors);
      throw new ApiError(
        detail ? `${response.data.message} — ${detail}` : response.data.message,
        response.data.code ?? "ERROR",
        response.status,
      );
    }
  }
  return { data: (response.data?.data ?? undefined) as T, envelope: response.data ?? { success: true, message: "" } };
}
