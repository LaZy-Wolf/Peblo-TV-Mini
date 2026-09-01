const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "peblo.cms.token";

export type FieldError = { code: string; message: string; field: string | null };

export class ApiError extends Error {
  status: number;
  errors: FieldError[];
  payload: unknown;

  constructor(status: number, errors: FieldError[], payload?: unknown) {
    super(errors[0]?.message ?? "Something went wrong.");
    this.status = status;
    this.errors = errors;
    this.payload = payload;
  }

  /** Errors belonging to one form field, so a form can show them in place. */
  forField(field: string): FieldError[] {
    return this.errors.filter((e) => e.field === field);
  }

  /** Errors with no field, which belong at the top of the form. */
  get general(): FieldError[] {
    return this.errors.filter((e) => !e.field);
  }
}

export const SESSION_EXPIRED_EVENT = "peblo:session-expired";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token === null) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, [
      {
        code: "network_error",
        message: "We could not reach the server. Check that the API is running, then try again.",
        field: null,
      },
    ]);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    // An expired or invalid token is a session problem, not a page problem.
    // Clear it and let the app fall back to the login screen, rather than
    // showing "something went wrong" with a retry button that can never work.
    if (response.status === 401 && !path.startsWith("/auth/login")) {
      setToken(null);
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const errors: FieldError[] = data?.errors ?? [
      { code: "unknown", message: "Something went wrong. Please try again.", field: null },
    ];
    throw new ApiError(response.status, errors, data);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T,>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T,>(path: string) => request<T>("DELETE", path),
};
