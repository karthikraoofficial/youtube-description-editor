/** Typed fetch wrapper. Every request carries the client header the backend requires (ADR-0006). */
/** FastAPI sends a string detail for our own errors and a list for schema validation errors. */
function describe(status: number, detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = (d.loc ?? []).filter((p) => p !== "body").slice(-1)[0];
        return field ? `${String(field)}: ${d.msg}` : (d.msg ?? "");
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(describe(status, detail));
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-YDE-Client": "1",
      ...init.headers,
    },
  });
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body);
  return body as T;
}

export type Health = { status: "ok"; fake: boolean };
