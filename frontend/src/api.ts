export interface Column { name: string; type: string; nullable?: boolean }
export interface OraError { code: string; message: string; offset: number; line: number | null }
export interface CompileError { line: number; position: number; text: string; attribute: string }
export interface StatementResult {
  sql: string; line: number; kind: string; keyword: string;
  status: "ok" | "warning" | "error";
  columns: Column[] | null; rows: unknown[][] | null; rowcount: number | null; truncated: boolean;
  elapsed_ms: number; dbms_output: string[]; message: string;
  error: OraError | null; compile_errors: CompileError[] | null;
}
export interface ScriptResponse {
  results: StatementResult[]; total_ms: number; transaction_pending: boolean; statements: number;
}
export interface Connection { id: string; label: string; kind: string; writable: boolean; dsn: string; user: string; editor: boolean }

export class ApiError extends Error {
  constructor(public status: number, public body: any) {
    super(typeof body?.detail === "string" ? body.detail : body?.message ?? body?.detail?.message ?? `HTTP ${status}`);
  }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export const api = {
  get: <T,>(url: string, params?: Record<string, string | number | boolean | undefined>) => {
    const qs = params
      ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString()
      : "";
    return request<T>("GET", url + qs);
  },
  post: <T,>(url: string, body?: unknown) => request<T>("POST", url, body ?? {}),
  del: <T,>(url: string) => request<T>("DELETE", url),
};

/** Id de sesión estable por pestaña del navegador (cada pestaña = su propia transacción). */
export const SESSION_ID: string = (() => {
  const key = "odl-session-id";
  try {
    const existing = sessionStorage.getItem(key);
    if (existing) return existing;
    const id = "web-" + crypto.randomUUID().replace(/-/g, "").slice(0, 20);
    sessionStorage.setItem(key, id);
    return id;
  } catch {
    return "web-" + Math.random().toString(36).slice(2, 14) + Date.now().toString(36);
  }
})();

export function store<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem("odl-" + key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}
export function save(key: string, value: unknown) {
  try { localStorage.setItem("odl-" + key, JSON.stringify(value)); } catch { /* sin almacenamiento */ }
}
