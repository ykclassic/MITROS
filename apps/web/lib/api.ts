export type ApiRequestInit = RequestInit & { timeoutMs?: number };

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function apiBaseUrl(): string {
  if (typeof window !== "undefined") return "";
  return process.env.MITROS_API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_MITROS_API_URL ?? "http://localhost:8000";
}

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : "/" + path;
  return apiBaseUrl() + normalized;
}

export async function fetchJson<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { timeoutMs = 15_000, ...requestInit } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(apiUrl(path), {
      ...requestInit,
      signal: controller.signal,
      cache: "no-store",
      headers: { Accept: "application/json", ...(requestInit.headers ?? {}) },
    });
    if (!response.ok) throw new ApiError(response.status, "API request failed (HTTP " + response.status + ")");
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}
