const RAW_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
export const API_BASE = RAW_BASE ? (RAW_BASE.endsWith("/api") ? RAW_BASE : `${RAW_BASE}/api`) : "/api";

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 800;

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function api(path: string, init?: RequestInit): Promise<Response> {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const fullPath = cleanPath.startsWith("/api/") || cleanPath === "/api"
    ? cleanPath
    : `${API_BASE}${cleanPath}`;

  const method = (init?.method || "GET").toUpperCase();
  // Never retry non-idempotent requests: replaying a POST /flights/search or
  // POST /chat/message can duplicate work (and duplicate scrapes/messages).
  const maxAttempts = method === "GET" || method === "HEAD" ? MAX_RETRIES : 0;

  let lastError: unknown = null;
  for (let attempt = 0; attempt <= maxAttempts; attempt++) {
    try {
      const res = await fetch(fullPath, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      });
      if (!res.ok) {
        const error = new Error(`API ${fullPath} ${res.status}`) as Error & {
          status?: number;
          isHttpError?: boolean;
        };
        error.status = res.status;
        error.isHttpError = true;
        throw error;
      }
      return res;
    } catch (err) {
      lastError = err;
      if ((err as { name?: string })?.name === "AbortError") break;
      // HTTP errors reached the server; retrying will not help.
      if ((err as { isHttpError?: boolean })?.isHttpError) break;
      const isNetworkError = err instanceof TypeError;
      if (!isNetworkError || attempt >= maxAttempts) break;
      await sleep(BASE_DELAY_MS * (2 ** attempt));
    }
  }
  throw lastError;
}
