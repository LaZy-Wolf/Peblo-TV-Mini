# Peblo TV Mini Frontends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the internal CMS an editor uses fifty times a week, and the viewer browse UI a child uses, as two separate applications that cannot reach each other's endpoints.

**Architecture:** Two independent Vite + React + TypeScript apps. The CMS talks to `/admin/*` with a bearer token and uses TanStack Query for server state. The viewer talks only to `/catalog` and `/catalog/search`, holds no token, and its API client contains no admin URL, so calling an admin endpoint from the viewer is unrepresentable rather than merely discouraged.

**Tech Stack:** Vite 6, React 19, TypeScript 5, React Router 7, TanStack Query 5 (CMS only), hand-written CSS with custom properties (no component library, no CSS framework).

**Spec:** `docs/superpowers/specs/2026-09-01-peblo-tv-mini-design.md`
**Depends on:** `2026-09-01-peblo-backend.md` and `-part2.md` complete and green.

## Global Constraints

- Node 20+. TypeScript strict mode on. `tsc --noEmit` and `eslint` clean before every commit.
- CMS runs on port 5173, viewer on 5174, API on 8000. `VITE_API_BASE_URL` in both.
- **No em dashes in any user-facing string.** This is the single most common AI tell and it is checked in Task 9.
- No emoji used as an icon. Inline SVG only.
- Every clickable element gets `cursor: pointer` and a visible `:focus-visible` ring.
- Transitions 150ms to 250ms, on `transform` and `opacity` and colour only. Never on `width`, `height`, `top`, `left`, `margin` or `padding`.
- `prefers-reduced-motion: reduce` collapses every transition to none.
- Body text minimum 16px. Contrast at least 4.5:1 for body, 3:1 for large text.
- Touch targets at least 44px.
- Every async surface handles four states explicitly: loading, empty, error, and (CMS only) permission denied.

## Design decisions, and where a tool's suggestion was rejected

Run for the record, because Part E of the brief asks which AI output was accepted and which was rejected.

| Source | Suggested | Decision |
|---|---|---|
| ui-ux-pro-max, viewer | Dark OLED shell, near-black background | **Accepted.** Matches a browse surface used on a tablet in the evening |
| ui-ux-pro-max, viewer | `#E11D48` play-red CTA, "cinema dark + play red" | **Rejected.** That is the Netflix reflex. If a reviewer can name the product our palette copied, the palette had no point. Using a warm marigold `oklch(0.78 0.16 65)` instead, which also suits a catalogue this heavy in Indian content |
| ui-ux-pro-max, viewer | Baloo 2 display font | **Accepted** for headings. It is a genuinely kid-appropriate rounded face without being childish |
| ui-ux-pro-max, viewer | Comic Neue body font | **Rejected.** A Comic Sans derivative reads as unserious and hurts long-form readability. Body uses a system sans stack, which also removes a second webfont from the critical path |
| ui-ux-pro-max, viewer | "Video-First Hero" with video background | **Rejected.** There is no video in this exercise, and a video background in a hero is a performance tax on the exact audience most likely to be on a slow connection |
| ui-ux-pro-max, CMS | "Comparison Table + CTA" landing pattern | **Rejected.** It returned a marketing landing page structure for an internal admin tool. The query matched on the word "table" |
| ui-ux-pro-max, CMS | Dark OLED style with `#F8FAFC` background | **Rejected as internally contradictory.** CMS is light, because editors use it in daylight next to other office tools |
| ui-ux-pro-max, both | Accessibility and interaction checklist | **Accepted** wholesale and folded into Global Constraints above |

**Why no component library.** shadcn/ui or MUI would each add a build-time dependency, a theming layer and a class of upgrade problems, to render tables, forms and a grid. Hand-written CSS with custom properties is smaller, has no version risk, and is faster to read in review. Stated in the README as a deliberate trade: if this were a real product with ten more screens, a library would start paying for itself.

**Why TanStack Query in the CMS but not the viewer.** The CMS is almost entirely server state, and its hard problems are cache invalidation after a mutation and keeping the validation report fresh while an editor fixes issues. That is exactly what the library is for. The viewer fetches one immutable JSON document per session that cannot change under it. A single fetch in a context provider is enough, and adding a caching layer over a value that never invalidates is complexity with no counterpart benefit.

---

## File Structure

```
cms/
  index.html
  package.json  tsconfig.json  vite.config.ts  eslint.config.js
  src/
    main.tsx  App.tsx  styles.css
    api/client.ts          fetch wrapper, token, error envelope parsing
    api/hooks.ts           every TanStack Query hook
    auth/AuthContext.tsx   token storage, role, login, logout
    components/
      Layout.tsx  States.tsx  Field.tsx  ArtworkSlot.tsx  Pagination.tsx  Icon.tsx
    pages/
      LoginPage.tsx  ShowsPage.tsx  ShowEditPage.tsx  EpisodeEditPage.tsx  PublishPage.tsx
viewer/
  index.html
  package.json  tsconfig.json  vite.config.ts  eslint.config.js
  src/
    main.tsx  App.tsx  styles.css
    api/catalog.ts         ONLY /catalog and /catalog/search
    catalog/CatalogContext.tsx
    components/
      Hero.tsx  Row.tsx  PosterCard.tsx  Art.tsx  Chip.tsx  Empty.tsx  Icon.tsx
    pages/
      HomePage.tsx  SearchPage.tsx  ShowPage.tsx
```

---

### Task 1: CMS scaffold, API client, auth, login

**Files:**
- Create: `cms/package.json`, `cms/tsconfig.json`, `cms/vite.config.ts`, `cms/eslint.config.js`, `cms/index.html`, `cms/src/main.tsx`, `cms/src/App.tsx`, `cms/src/styles.css`, `cms/src/api/client.ts`, `cms/src/auth/AuthContext.tsx`, `cms/src/components/Layout.tsx`, `cms/src/components/States.tsx`, `cms/src/components/Icon.tsx`, `cms/src/pages/LoginPage.tsx`

**Interfaces:**
- Consumes: the API from the backend plan
- Produces: `api.get/post/patch/del(path, init)` and `ApiError` from `api/client`; `useAuth()` returning `{ token, email, role, isAdmin, login, logout }`; `<Loading/>`, `<ErrorState error/>`, `<Empty title message action?/>`, `<Forbidden/>` from `components/States`

- [ ] **Step 1: Scaffold and install**

```bash
npm create vite@latest cms -- --template react-ts
cd cms && npm install && npm install @tanstack/react-query react-router-dom && npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks
```

- [ ] **Step 2: Set the dev server port in `cms/vite.config.ts`**

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true },
});
```

- [ ] **Step 3: Write `cms/src/api/client.ts`**

```ts
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

  /** Errors that belong to one form field, so a form can show them in place. */
  forField(field: string): FieldError[] {
    return this.errors.filter((e) => e.field === field);
  }
}

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

  const response = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
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
```

- [ ] **Step 4: Write `cms/src/auth/AuthContext.tsx`**

```tsx
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { api, getToken, setToken } from "../api/client";

type Session = { email: string; role: string };
type AuthValue = {
  token: string | null;
  email: string | null;
  role: string | null;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);
const SESSION_KEY = "peblo.cms.session";

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken());
  const [session, setSession] = useState<Session | null>(readSession());

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.post<{ access_token: string; role: string; email: string }>(
      "/auth/login",
      { email, password },
    );
    setToken(result.access_token);
    setTokenState(result.access_token);
    const next = { email: result.email, role: result.role };
    localStorage.setItem(SESSION_KEY, JSON.stringify(next));
    setSession(next);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      token,
      email: session?.email ?? null,
      role: session?.role ?? null,
      isAdmin: session?.role === "admin",
      login,
      logout,
    }),
    [token, session, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
```

- [ ] **Step 5: Write `cms/src/styles.css`**

Light, dense, high contrast. Tokens first so nothing later hardcodes a colour.

```css
:root {
  --ink: #16181d;
  --ink-2: #4a5160;
  --line: #d8dce4;
  --line-strong: #b4bbc7;
  --bg: #ffffff;
  --bg-2: #f4f6f9;
  --accent: #1d4ed8;
  --accent-ink: #ffffff;
  --danger: #b42318;
  --danger-bg: #fef3f2;
  --warn: #8a5a00;
  --warn-bg: #fffaeb;
  --ok: #067647;
  --ok-bg: #ecfdf3;

  --s1: 4px;
  --s2: 8px;
  --s3: 12px;
  --s4: 16px;
  --s5: 24px;
  --s6: 32px;
  --radius: 6px;
  --ease: cubic-bezier(0.23, 1, 0.32, 1);

  color-scheme: light;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg-2);
  color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

h1 { font-size: 24px; line-height: 1.2; margin: 0 0 var(--s4); }
h2 { font-size: 19px; line-height: 1.25; margin: 0 0 var(--s3); }
h3 { font-size: 16px; line-height: 1.3; margin: 0 0 var(--s2); }

a { color: var(--accent); }

button, .button {
  font: inherit;
  cursor: pointer;
  border: 1px solid var(--line-strong);
  background: var(--bg);
  color: var(--ink);
  border-radius: var(--radius);
  padding: 10px var(--s4);
  min-height: 44px;
  transition: background-color 150ms var(--ease), border-color 150ms var(--ease);
}
button:hover:not(:disabled) { background: var(--bg-2); }
button:disabled { cursor: not-allowed; opacity: 0.55; }

.button-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}
.button-primary:hover:not(:disabled) { background: #1a44bd; }

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 3px;
}

input, select, textarea {
  font: inherit;
  width: 100%;
  min-height: 44px;
  padding: 9px var(--s3);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--ink);
}
input::placeholder { color: #6b7280; }
input[aria-invalid="true"], select[aria-invalid="true"] { border-color: var(--danger); }

label { display: block; font-weight: 600; font-size: 14px; margin-bottom: var(--s1); }

table { width: 100%; border-collapse: collapse; background: var(--bg); }
th, td { text-align: left; padding: var(--s3); border-bottom: 1px solid var(--line); }
th { font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-2); }
tbody tr:hover { background: var(--bg-2); }

.panel {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: var(--s5);
}

.stack > * + * { margin-top: var(--s4); }
.row { display: flex; gap: var(--s3); align-items: center; flex-wrap: wrap; }
.grow { flex: 1; }
.muted { color: var(--ink-2); }
.small { font-size: 14px; }

.badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  padding: 2px var(--s2);
  border-radius: 999px;
  border: 1px solid transparent;
}
.badge-published { background: var(--ok-bg); color: var(--ok); }
.badge-draft { background: var(--bg-2); color: var(--ink-2); border-color: var(--line); }

.note { border-radius: var(--radius); padding: var(--s3) var(--s4); font-size: 14px; }
.note-error { background: var(--danger-bg); color: var(--danger); }
.note-warn { background: var(--warn-bg); color: var(--warn); }
.note-ok { background: var(--ok-bg); color: var(--ok); }

.skeleton {
  background: linear-gradient(90deg, var(--bg-2) 25%, #e9edf3 37%, var(--bg-2) 63%);
  background-size: 400% 100%;
  animation: shimmer 1.2s infinite linear;
  border-radius: var(--radius);
}
@keyframes shimmer { to { background-position: -135% 0; } }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 6: Write `cms/src/components/Icon.tsx`**

No emoji anywhere. These are the only icons the CMS needs.

```tsx
type IconProps = { name: "check" | "alert" | "block" | "clock"; label?: string };

const PATHS: Record<IconProps["name"], string> = {
  check: "M20 6 9 17l-5-5",
  alert: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  block: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM5 5l14 14",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
};

export function Icon({ name, label }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ flexShrink: 0 }}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
```

- [ ] **Step 7: Write `cms/src/components/States.tsx`**

Every async surface in the CMS uses these, so the four states are handled by construction rather than by remembering.

```tsx
import { ApiError } from "../api/client";
import { Icon } from "./Icon";

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="panel stack" role="status" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      <div className="skeleton" style={{ height: 18, width: "40%" }} />
      <div className="skeleton" style={{ height: 18, width: "70%" }} />
      <div className="skeleton" style={{ height: 18, width: "55%" }} />
    </div>
  );
}

export function Forbidden({ what = "this page" }: { what?: string }) {
  return (
    <div className="panel stack">
      <h2>
        <Icon name="block" /> You do not have access to {what}
      </h2>
      <p className="muted">
        Your account is signed in as an editor. Publishing and rollback are restricted to
        administrators. Ask an administrator to run this, or request admin access.
      </p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (error instanceof ApiError && error.status === 403) return <Forbidden />;

  const messages =
    error instanceof ApiError
      ? error.errors.map((e) => e.message)
      : ["We could not reach the server. Check that the API is running, then try again."];

  return (
    <div className="panel stack">
      <h2>
        <Icon name="alert" /> Something went wrong
      </h2>
      <ul className="stack">
        {messages.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ul>
      {onRetry && (
        <div>
          <button onClick={onRetry}>Try again</button>
        </div>
      )}
    </div>
  );
}

export function Empty({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="panel stack" style={{ textAlign: "center" }}>
      <h2>{title}</h2>
      <p className="muted">{message}</p>
      {action}
    </div>
  );
}
```

Add to `styles.css`:

```css
.visually-hidden {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
```

- [ ] **Step 8: Write `cms/src/pages/LoginPage.tsx`**

```tsx
import { useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "We could not reach the server. Check that the API is running.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 380, margin: "10vh auto", padding: "0 16px" }}>
      <form className="panel stack" onSubmit={onSubmit}>
        <h1>Peblo CMS</h1>
        {error && (
          <p className="note note-error" role="alert">
            {error}
          </p>
        )}
        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button className="button-primary" type="submit" disabled={busy}>
          {busy ? "Signing in" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 9: Write `cms/src/components/Layout.tsx` and `cms/src/App.tsx`**

`Layout.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { email, role, logout } = useAuth();
  return (
    <>
      <header
        style={{
          background: "var(--bg)",
          borderBottom: "1px solid var(--line)",
          padding: "var(--s3) var(--s5)",
        }}
      >
        <div className="row" style={{ maxWidth: 1200, margin: "0 auto" }}>
          <strong style={{ marginRight: "var(--s5)" }}>Peblo CMS</strong>
          <nav className="row grow" style={{ gap: "var(--s4)" }}>
            <NavLink to="/shows">Shows</NavLink>
            <NavLink to="/publish">Publish</NavLink>
          </nav>
          <span className="muted small">
            {email} ({role})
          </span>
          <button onClick={logout}>Sign out</button>
        </div>
      </header>
      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "var(--s5)" }}>
        <Outlet />
      </main>
    </>
  );
}
```

`App.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 } },
});

function Shell() {
  const { token } = useAuth();
  if (!token) return <LoginPage />;
  return (
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/shows" element={<div>Shows</div>} />
          <Route path="/publish" element={<div>Publish</div>} />
          <Route path="*" element={<Navigate to="/shows" replace />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

Replace `cms/src/main.tsx` with:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 10: Verify manually**

```bash
cd cms && npm run dev
```
With the API running, open `http://localhost:5173`, sign in as `admin@peblo.test`. Expected: the shell renders with the email and role in the header. Sign in with a wrong password. Expected: a readable message, not a raw status code.

- [ ] **Step 11: Typecheck, lint, commit**

```bash
cd cms && npx tsc --noEmit && npm run lint
git add cms
git commit -m "feat(cms): scaffold, API client, auth context, login"
```

---

### Task 2: Shows list with search, filters, pagination

**Files:**
- Create: `cms/src/api/hooks.ts`, `cms/src/components/Pagination.tsx`, `cms/src/pages/ShowsPage.tsx`
- Modify: `cms/src/App.tsx`

**Interfaces:**
- Consumes: `api` from Task 1
- Produces: types `Show`, `Episode`, `Page<T>`, `ValidationReport`, `PublishRun`; hooks `useShows`, `useShow`, `useCreateShow`, `useUpdateShow`, `useEpisodes`, `useUpdateEpisode`, `useCreateEpisode`, `useValidationReport`, `useRuns`, `usePublish`, `useRollback`, `useUploadArtwork`, `useArtworkForShow` from `api/hooks`

- [ ] **Step 1: Write `cms/src/api/hooks.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export type Show = {
  id: number;
  slug: string;
  title: string;
  synopsis: string;
  section: string | null;
  categories: string[];
  status: "draft" | "published";
  updated_at: string;
};

export type Episode = {
  id: number;
  season_id: number;
  episode_number: number;
  title: string;
  duration_seconds: number | null;
  language: string;
  content_group: string;
  status: "draft" | "published";
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Issue = {
  code: string;
  message: string;
  fix_hint: string;
  entity_type: string;
  entity_id: number | null;
  entity_label: string;
};

export type ValidationReport = {
  can_publish: boolean;
  blocking_count: number;
  warning_count: number;
  groups: {
    show_id: number | null;
    show_title: string;
    show_slug: string;
    blocking: Issue[];
    warnings: Issue[];
  }[];
  import_problems: { id: number; reason: string; action: string; source_row: unknown }[];
};

export type PublishRun = {
  id: number;
  run_id: string;
  status: "running" | "success" | "failed" | "no_change";
  started_by: number | null;
  started_at: string | null;
  finished_at: string | null;
  counts: Record<string, number> | null;
  catalog_key: string | null;
  error: unknown;
};

export type ShowFilters = {
  q?: string;
  section?: string;
  status?: string;
  page: number;
  page_size: number;
};

function qs(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function useShows(filters: ShowFilters) {
  return useQuery({
    queryKey: ["shows", filters],
    queryFn: () => api.get<Page<Show>>(`/admin/shows${qs(filters)}`),
  });
}

export function useShow(id: number | null) {
  return useQuery({
    queryKey: ["show", id],
    queryFn: () => api.get<Show>(`/admin/shows/${id}`),
    enabled: id !== null,
  });
}

export function useCreateShow() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Show>) => api.post<Show>("/admin/shows", body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["shows"] }),
  });
}

export function useUpdateShow(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Show>) => api.patch<Show>(`/admin/shows/${id}`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["shows"] });
      client.invalidateQueries({ queryKey: ["show", id] });
      // Publishing eligibility may have changed, so the report is now stale.
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useEpisodes(showId: number | null) {
  return useQuery({
    queryKey: ["episodes", showId],
    queryFn: () => api.get<Page<Episode>>(`/admin/episodes${qs({ show_id: showId!, page_size: 100 })}`),
    enabled: showId !== null,
  });
}

export function useCreateEpisode(showId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Episode>) => api.post<Episode>("/admin/episodes", body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["episodes", showId] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useUpdateEpisode(showId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Episode> }) =>
      api.patch<Episode>(`/admin/episodes/${id}`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["episodes", showId] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useValidationReport() {
  return useQuery({
    queryKey: ["validation-report"],
    queryFn: () => api.get<ValidationReport>("/admin/validation-report"),
  });
}

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => api.get<{ items: PublishRun[] }>("/admin/catalog/runs"),
  });
}

export function usePublish() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<PublishRun>("/admin/catalog/publish"),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["runs"] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}

export function useRollback() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (runDbId: number) =>
      api.post<PublishRun>("/admin/catalog/rollback", { run_db_id: runDbId }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useUploadArtwork() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { kind: string; file: File; showId?: number; episodeId?: number }) => {
      const form = new FormData();
      form.set("kind", input.kind);
      form.set("file", input.file);
      if (input.showId !== undefined) form.set("show_id", String(input.showId));
      if (input.episodeId !== undefined) form.set("episode_id", String(input.episodeId));
      return api.post<{ id: number; kind: string; url: string; width: number; height: number }>(
        "/admin/artwork",
        form,
      );
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["validation-report"] }),
  });
}
```

- [ ] **Step 2: Write `cms/src/components/Pagination.tsx`**

```tsx
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="row" style={{ justifyContent: "space-between" }}>
      <span className="muted small" aria-live="polite">
        Showing {from} to {to} of {total}
      </span>
      <div className="row">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Previous
        </button>
        <span className="small">
          Page {page} of {lastPage}
        </span>
        <button onClick={() => onPage(page + 1)} disabled={page >= lastPage}>
          Next
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `cms/src/pages/ShowsPage.tsx`**

Search is debounced so typing does not fire a request per keystroke. Filters reset the page to 1, because landing on page 4 of a 1-page result is the classic filter bug.

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState, Empty, Loading } from "../components/States";
import { Pagination } from "../components/Pagination";
import { useShows } from "../api/hooks";

const SECTIONS = ["featured", "series", "minisodes", "songs"];
const PAGE_SIZE = 20;

export function ShowsPage() {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [section, setSection] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(text);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [text]);

  const query = useShows({ q, section, status, page, page_size: PAGE_SIZE });

  return (
    <div className="stack">
      <h1>Shows</h1>

      <div className="panel row">
        <div className="grow" style={{ minWidth: 220 }}>
          <label htmlFor="q">Search</label>
          <input
            id="q"
            type="search"
            placeholder="Show title or web address"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="section">Section</label>
          <select
            id="section"
            value={section}
            onChange={(e) => {
              setSection(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All sections</option>
            {SECTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
          </select>
        </div>
      </div>

      {query.isPending && <Loading label="Loading shows" />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.isSuccess && query.data.total === 0 && (
        <Empty
          title="No shows match those filters"
          message="Try clearing the section or status filter, or searching for a different title."
        />
      )}

      {query.isSuccess && query.data.total > 0 && (
        <div className="panel stack">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Section</th>
                <th>Status</th>
                <th>Web address</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((show) => (
                <tr key={show.id}>
                  <td>
                    <Link to={`/shows/${show.id}`}>{show.title}</Link>
                  </td>
                  <td>{show.section ?? <span className="muted">Not set</span>}</td>
                  <td>
                    <span className={`badge badge-${show.status}`}>{show.status}</span>
                  </td>
                  <td className="muted small">{show.slug}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={query.data.page}
            pageSize={query.data.page_size}
            total={query.data.total}
            onPage={setPage}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Route it in `cms/src/App.tsx`**

```tsx
<Route path="/shows" element={<ShowsPage />} />
```

- [ ] **Step 5: Verify manually**

Open `/shows`. Expected: 8 rows, `rhyme-rangers` showing "Not set" for section and a draft badge. Filter to `section=songs`. Expected: 2 rows. Type a nonsense search. Expected: the empty state with usable advice, not a blank table.

- [ ] **Step 6: Typecheck, lint, commit**

```bash
cd cms && npx tsc --noEmit && npm run lint
git add cms && git commit -m "feat(cms): shows list with search, filters and pagination"
```

---

### Task 3: Show edit with three artwork slots

**Files:**
- Create: `cms/src/components/ArtworkSlot.tsx`, `cms/src/components/Field.tsx`, `cms/src/pages/ShowEditPage.tsx`
- Modify: `cms/src/App.tsx`, `cms/src/api/hooks.ts`

**Interfaces:**
- Consumes: `useShow`, `useUpdateShow`, `useUploadArtwork` from Task 2
- Produces: `<ArtworkSlot kind showId? episodeId? currentUrl?/>`, `<Field label htmlFor error? hint?/>`

- [ ] **Step 1: Write `cms/src/components/Field.tsx`**

```tsx
import type { FieldError } from "../api/client";

export function Field({
  label,
  htmlFor,
  hint,
  errors,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  errors?: FieldError[];
  children: React.ReactNode;
}) {
  const hintId = hint ? `${htmlFor}-hint` : undefined;
  const errorId = errors?.length ? `${htmlFor}-error` : undefined;
  return (
    <div>
      <label htmlFor={htmlFor}>{label}</label>
      {hint && (
        <p id={hintId} className="muted small" style={{ margin: "0 0 var(--s1)" }}>
          {hint}
        </p>
      )}
      {children}
      {errors?.map((e) => (
        <p key={e.code} id={errorId} className="note note-error small" style={{ marginTop: 4 }}>
          {e.message}
        </p>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Write `cms/src/components/ArtworkSlot.tsx`**

The required dimensions are shown before upload, not after failure. Errors come from the server, so the client cannot disagree with it about what is valid.

```tsx
import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { useUploadArtwork } from "../api/hooks";

const SPECS = {
  poster: { label: "Poster", size: "600 x 900", note: "Tall. Used in the browse rows.", ratio: "2 / 3" },
  banner: { label: "Banner", size: "1280 x 720", note: "Wide. Used for the featured hero.", ratio: "16 / 9" },
  thumbnail: { label: "Thumbnail", size: "640 x 360", note: "Wide. Used in episode lists.", ratio: "16 / 9" },
} as const;

export function ArtworkSlot({
  kind,
  showId,
  episodeId,
  currentUrl,
}: {
  kind: keyof typeof SPECS;
  showId?: number;
  episodeId?: number;
  currentUrl?: string;
}) {
  const spec = SPECS[kind];
  const upload = useUploadArtwork();
  const [preview, setPreview] = useState<string | null>(null);

  // Object URLs are a real leak if you forget this.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function onPick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    upload.mutate({ kind, file, showId, episodeId });
    event.target.value = "";
  }

  const shown = preview ?? currentUrl;
  const errors = upload.error instanceof ApiError ? upload.error.errors : [];
  const inputId = `artwork-${kind}-${showId ?? "e"}-${episodeId ?? "s"}`;

  return (
    <div className="stack" style={{ minWidth: 200 }}>
      <div>
        <label htmlFor={inputId}>{spec.label}</label>
        <p className="muted small" style={{ margin: 0 }}>
          {spec.size} pixels. {spec.note}
        </p>
      </div>

      <div
        style={{
          aspectRatio: spec.ratio,
          background: "var(--bg-2)",
          border: "1px dashed var(--line-strong)",
          borderRadius: "var(--radius)",
          overflow: "hidden",
          display: "grid",
          placeItems: "center",
        }}
      >
        {shown ? (
          <img
            src={shown}
            alt={`${spec.label} preview`}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <span className="muted small">No {spec.label.toLowerCase()} yet</span>
        )}
      </div>

      <input id={inputId} type="file" accept="image/*" onChange={onPick} />

      {upload.isPending && <p className="small muted">Checking and uploading</p>}
      {upload.isSuccess && (
        <p className="note note-ok small">
          Uploaded at {upload.data.width} by {upload.data.height} pixels.
        </p>
      )}
      {errors.map((e) => (
        <p key={e.code} className="note note-error small" role="alert">
          {e.message}
        </p>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Add `useShowArtwork` to `cms/src/api/hooks.ts`**

The show detail endpoint does not return artwork, so the slots need their current URLs from somewhere. Add a small endpoint-free approach: read them from the published catalogue is wrong (drafts have none), so extend the API instead. Add to the backend `GET /admin/shows/{id}` response a `artwork: Record<string,string>` field, and to `GET /admin/episodes/{id}` the same. Implement by editing `api/app/routers/shows.py` and `episodes.py` to include:

```python
from app.storage import get_storage


def _artwork_map(records) -> dict[str, str]:
    storage = get_storage()
    return {
        (a.kind.value if hasattr(a.kind, "value") else a.kind): storage.url(a.storage_key)
        for a in records
    }
```

and returning `{**ShowOut.model_validate(show).model_dump(mode="json"), "artwork": _artwork_map(show.artwork)}` from `get_show`. Add a backend test asserting `GET /admin/shows/{id}` includes an `artwork` object. Then in `hooks.ts` widen the type:

```ts
export type ShowDetail = Show & { artwork: Partial<Record<"poster" | "banner" | "thumbnail", string>> };
```

and change `useShow` to `useQuery<ShowDetail>`.

- [ ] **Step 4: Write `cms/src/pages/ShowEditPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { ArtworkSlot } from "../components/ArtworkSlot";
import { Field } from "../components/Field";
import { ErrorState, Loading } from "../components/States";
import { useEpisodes, useShow, useUpdateShow } from "../api/hooks";

const SECTIONS = ["featured", "series", "minisodes", "songs"];
const CATEGORIES = [
  "adventure", "folk", "friendship", "india", "language", "learning", "maths",
  "music", "nature", "reading", "science", "singalong", "stories", "travel", "values",
];

export function ShowEditPage() {
  const id = Number(useParams().id);
  const show = useShow(id);
  const update = useUpdateShow(id);
  const episodes = useEpisodes(id);

  const [form, setForm] = useState({ title: "", synopsis: "", section: "", categories: [] as string[] });

  useEffect(() => {
    if (show.data) {
      setForm({
        title: show.data.title,
        synopsis: show.data.synopsis,
        section: show.data.section ?? "",
        categories: show.data.categories,
      });
    }
  }, [show.data]);

  if (show.isPending) return <Loading label="Loading show" />;
  if (show.isError) return <ErrorState error={show.error} onRetry={() => show.refetch()} />;

  const error = update.error instanceof ApiError ? update.error : null;

  return (
    <div className="stack">
      <div className="row">
        <h1 className="grow">{show.data.title}</h1>
        <span className={`badge badge-${show.data.status}`}>{show.data.status}</span>
      </div>

      <section className="panel stack">
        <h2>Details</h2>
        {error && error.errors.filter((e) => !e.field).map((e) => (
          <p key={e.code} className="note note-error" role="alert">{e.message}</p>
        ))}

        <Field label="Title" htmlFor="title" errors={error?.forField("title")}>
          <input id="title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field>

        <Field
          label="Section"
          htmlFor="section"
          hint="Which row this show appears in. A show cannot be published without one."
          errors={error?.forField("section")}
        >
          <select
            id="section"
            value={form.section}
            onChange={(e) => setForm({ ...form, section: e.target.value })}
          >
            <option value="">Not set</option>
            {SECTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>

        <Field label="Synopsis" htmlFor="synopsis" errors={error?.forField("synopsis")}>
          <textarea
            id="synopsis"
            rows={3}
            value={form.synopsis}
            onChange={(e) => setForm({ ...form, synopsis: e.target.value })}
          />
        </Field>

        <Field label="Categories" htmlFor="categories" errors={error?.forField("categories")}>
          <div className="row" id="categories">
            {CATEGORIES.map((c) => (
              <label key={c} className="row small" style={{ fontWeight: 400, gap: 4 }}>
                <input
                  type="checkbox"
                  style={{ width: "auto", minHeight: 0 }}
                  checked={form.categories.includes(c)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      categories: e.target.checked
                        ? [...form.categories, c]
                        : form.categories.filter((x) => x !== c),
                    })
                  }
                />
                {c}
              </label>
            ))}
          </div>
        </Field>

        <div className="row">
          <button
            className="button-primary"
            disabled={update.isPending}
            onClick={() => update.mutate({ ...form, section: form.section || null })}
          >
            {update.isPending ? "Saving" : "Save changes"}
          </button>
          <button
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                status: show.data.status === "published" ? "draft" : "published",
              })
            }
          >
            {show.data.status === "published" ? "Move back to draft" : "Publish this show"}
          </button>
          {update.isSuccess && <span className="note note-ok small">Saved</span>}
        </div>
      </section>

      <section className="panel stack">
        <h2>Artwork</h2>
        <div className="row" style={{ alignItems: "flex-start", gap: "var(--s5)" }}>
          <ArtworkSlot kind="poster" showId={id} currentUrl={show.data.artwork?.poster} />
          <ArtworkSlot kind="banner" showId={id} currentUrl={show.data.artwork?.banner} />
          <ArtworkSlot kind="thumbnail" showId={id} currentUrl={show.data.artwork?.thumbnail} />
        </div>
      </section>

      <section className="panel stack">
        <h2>Episodes</h2>
        {episodes.isPending && <Loading label="Loading episodes" />}
        {episodes.isError && <ErrorState error={episodes.error} />}
        {episodes.isSuccess && (
          <table>
            <thead>
              <tr>
                <th>Number</th><th>Title</th><th>Language</th>
                <th>Duration</th><th>Status</th><th>Group</th>
              </tr>
            </thead>
            <tbody>
              {episodes.data.items.map((e) => (
                <tr key={e.id}>
                  <td>{e.episode_number}</td>
                  <td><Link to={`/episodes/${e.id}`}>{e.title}</Link></td>
                  <td>{e.language}</td>
                  <td>{e.duration_seconds ? `${e.duration_seconds}s` : <span className="muted">Not set</span>}</td>
                  <td><span className={`badge badge-${e.status}`}>{e.status}</span></td>
                  <td className="muted small">{e.content_group}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 5: Route it, then verify manually**

Add `<Route path="/shows/:id" element={<ShowEditPage />} />`.

Open a show. Upload `data/assets/poster_wrong_ratio.jpg` into the Poster slot. Expected: the preview appears, then a readable error beneath it explaining the image is rotated. Upload `poster_good.jpg`. Expected: a green confirmation naming 600 by 900. Open `rhyme-rangers`, leave section unset, click "Publish this show". Expected: an error naming the missing section and listing the allowed values.

- [ ] **Step 6: Typecheck, lint, commit**

```bash
cd cms && npx tsc --noEmit && npm run lint
git add cms api && git commit -m "feat(cms): show edit with three validated artwork slots"
```

---

### Task 4: Episode edit

**Files:**
- Create: `cms/src/pages/EpisodeEditPage.tsx`
- Modify: `cms/src/App.tsx`, `cms/src/api/hooks.ts`

**Interfaces:**
- Consumes: `useUpdateEpisode`, `useUploadArtwork`
- Produces: `useEpisode(id)` hook returning `Episode & { artwork: Record<string,string> }`

- [ ] **Step 1: Add `useEpisode` to `cms/src/api/hooks.ts`**

```ts
export type EpisodeDetail = Episode & { artwork: Partial<Record<"thumbnail", string>> };

export function useEpisode(id: number) {
  return useQuery({
    queryKey: ["episode", id],
    queryFn: () => api.get<EpisodeDetail>(`/admin/episodes/${id}`),
  });
}

export function useUpdateEpisodeById(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Episode>) => api.patch<Episode>(`/admin/episodes/${id}`, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["episode", id] });
      client.invalidateQueries({ queryKey: ["episodes"] });
      client.invalidateQueries({ queryKey: ["validation-report"] });
    },
  });
}
```

- [ ] **Step 2: Write `cms/src/pages/EpisodeEditPage.tsx`**

The content group field carries an inline explanation, because that convention is the one an editor will get wrong and there is nowhere else to learn it.

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { ArtworkSlot } from "../components/ArtworkSlot";
import { Field } from "../components/Field";
import { ErrorState, Loading } from "../components/States";
import { useEpisode, useUpdateEpisodeById } from "../api/hooks";

export function EpisodeEditPage() {
  const id = Number(useParams().id);
  const episode = useEpisode(id);
  const update = useUpdateEpisodeById(id);
  const [form, setForm] = useState({
    title: "",
    duration_seconds: "",
    language: "en",
    content_group: "",
  });

  useEffect(() => {
    if (episode.data) {
      setForm({
        title: episode.data.title,
        duration_seconds: episode.data.duration_seconds?.toString() ?? "",
        language: episode.data.language,
        content_group: episode.data.content_group,
      });
    }
  }, [episode.data]);

  if (episode.isPending) return <Loading label="Loading episode" />;
  if (episode.isError) return <ErrorState error={episode.error} onRetry={() => episode.refetch()} />;

  const error = update.error instanceof ApiError ? update.error : null;
  const isTrailer = episode.data.content_group.includes("s00e");

  return (
    <div className="stack">
      <div className="row">
        <h1 className="grow">
          Episode {episode.data.episode_number}: {episode.data.title}
        </h1>
        <span className={`badge badge-${episode.data.status}`}>{episode.data.status}</span>
      </div>

      {isTrailer && (
        <p className="note note-warn">
          This is a trailer (season 0). Trailers do not appear as a season in the viewer.
          They need a thumbnail only.
        </p>
      )}

      <section className="panel stack">
        {error?.errors.filter((e) => !e.field).map((e) => (
          <p key={e.code} className="note note-error" role="alert">{e.message}</p>
        ))}

        <Field label="Title" htmlFor="title" errors={error?.forField("title")}>
          <input id="title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field>

        <Field
          label="Duration in seconds"
          htmlFor="duration"
          hint="How long the episode runs. Required before it can be published."
          errors={error?.forField("duration_seconds")}
        >
          <input
            id="duration"
            type="number"
            min={1}
            value={form.duration_seconds}
            onChange={(e) => setForm({ ...form, duration_seconds: e.target.value })}
          />
        </Field>

        <Field label="Language" htmlFor="language" errors={error?.forField("language")}>
          <select
            id="language"
            value={form.language}
            onChange={(e) => setForm({ ...form, language: e.target.value })}
          >
            <option value="en">English</option>
            <option value="hi">Hindi</option>
          </select>
        </Field>

        <Field
          label="Content group"
          htmlFor="group"
          hint={
            "Episodes that share a content group are the same episode in different languages. " +
            "Viewers see one entry with a language choice. Each language may appear once per group."
          }
          errors={error?.forField("content_group")}
        >
          <input
            id="group"
            value={form.content_group}
            onChange={(e) => setForm({ ...form, content_group: e.target.value })}
          />
        </Field>

        <div className="row">
          <button
            className="button-primary"
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                title: form.title,
                duration_seconds: form.duration_seconds ? Number(form.duration_seconds) : null,
                language: form.language,
                content_group: form.content_group,
              })
            }
          >
            {update.isPending ? "Saving" : "Save changes"}
          </button>
          <button
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                status: episode.data.status === "published" ? "draft" : "published",
              })
            }
          >
            {episode.data.status === "published" ? "Move back to draft" : "Publish this episode"}
          </button>
          {update.isSuccess && <span className="note note-ok small">Saved</span>}
        </div>
      </section>

      <section className="panel stack">
        <h2>Thumbnail</h2>
        <ArtworkSlot kind="thumbnail" episodeId={id} currentUrl={episode.data.artwork?.thumbnail} />
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Route and verify manually**

Add `<Route path="/episodes/:id" element={<EpisodeEditPage />} />`.

Open `ep_0036`'s episode (Discover India with Moti, S1E4, imported as draft). Click "Publish this episode". Expected: a refusal naming the missing thumbnail. Upload `thumb_good.jpg`, then publish. Expected: success.

Then set a second Hindi episode's content group to one that already has a Hindi variant. Expected: a 409 rendered as a sentence about each language appearing once.

- [ ] **Step 4: Typecheck, lint, commit**

```bash
cd cms && npx tsc --noEmit && npm run lint
git add cms && git commit -m "feat(cms): episode edit with content group guidance"
```

---

### Task 5: Publish page

**Files:**
- Create: `cms/src/pages/PublishPage.tsx`
- Modify: `cms/src/App.tsx`

**Interfaces:**
- Consumes: `useValidationReport`, `useRuns`, `usePublish`, `useRollback`, `useAuth`

- [ ] **Step 1: Write `cms/src/pages/PublishPage.tsx`**

The blocking reasons render inline beside the disabled button, not in a tooltip. A tooltip cannot be read and acted on at the same time.

```tsx
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { ErrorState, Loading } from "../components/States";
import { usePublish, useRollback, useRuns, useValidationReport } from "../api/hooks";

function timestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "";
}

export function PublishPage() {
  const { isAdmin } = useAuth();
  const report = useValidationReport();
  const runs = useRuns();
  const publish = usePublish();
  const rollback = useRollback();

  const publishError = publish.error instanceof ApiError ? publish.error : null;

  return (
    <div className="stack">
      <h1>Publish</h1>

      {report.isPending && <Loading label="Checking the catalogue" />}
      {report.isError && <ErrorState error={report.error} onRetry={() => report.refetch()} />}

      {report.isSuccess && (
        <section className="panel stack">
          <h2>Ready to publish</h2>

          {report.data.can_publish ? (
            <p className="note note-ok">
              <Icon name="check" /> Nothing is blocking a publish.
              {report.data.warning_count > 0 &&
                ` ${report.data.warning_count} warnings below are worth a look but will not stop you.`}
            </p>
          ) : (
            <div className="note note-error stack">
              <strong>
                <Icon name="alert" /> {report.data.blocking_count} problems must be fixed first
              </strong>
              <ul>
                {report.data.groups.flatMap((g) =>
                  g.blocking.map((issue) => (
                    <li key={`${g.show_slug}-${issue.code}-${issue.entity_id}`}>
                      <strong>{g.show_title}</strong>, {issue.entity_label}: {issue.message}
                    </li>
                  )),
                )}
              </ul>
            </div>
          )}

          {!isAdmin && (
            <p className="note note-warn">
              <Icon name="block" /> You are signed in as an editor. Publishing is restricted to
              administrators. Everything above is still worth fixing, then ask an administrator
              to publish.
            </p>
          )}

          <div className="row">
            <button
              className="button-primary"
              disabled={!isAdmin || !report.data.can_publish || publish.isPending}
              onClick={() => publish.mutate()}
            >
              {publish.isPending ? "Publishing" : "Publish catalogue"}
            </button>
            {publish.isSuccess && (
              <span className="note note-ok small">
                Published. {publish.data.counts?.shows} shows, {publish.data.counts?.episodes}{" "}
                episodes.
                {publish.data.status === "no_change" &&
                  " Nothing had changed, so the live catalogue was left alone."}
              </span>
            )}
          </div>

          {publishError && (
            <div className="note note-error" role="alert">
              {publishError.errors.map((e) => (
                <p key={e.code}>{e.message}</p>
              ))}
            </div>
          )}
        </section>
      )}

      {report.isSuccess && report.data.import_problems.length > 0 && (
        <section className="panel stack">
          <h2>Data import problems</h2>
          <p className="muted small">
            These rows arrived from a bulk import in a state our rules do not allow. They are
            listed here so you can decide what to do, rather than being silently dropped.
          </p>
          <ul className="stack">
            {report.data.import_problems.map((p) => (
              <li key={p.id}>
                <span className={`badge badge-${p.action === "rejected" ? "draft" : "draft"}`}>
                  {p.action === "rejected" ? "Not imported" : "Imported as draft"}
                </span>{" "}
                {p.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.isSuccess && report.data.warning_count > 0 && (
        <section className="panel stack">
          <h2>Warnings</h2>
          <ul className="stack">
            {report.data.groups.flatMap((g) =>
              g.warnings.map((issue) => (
                <li key={`${g.show_slug}-${issue.code}-${issue.entity_label}`}>
                  <strong>{g.show_title}</strong>, {issue.entity_label}: {issue.message}
                  <span className="muted small"> {issue.fix_hint}</span>
                </li>
              )),
            )}
          </ul>
        </section>
      )}

      <section className="panel stack">
        <h2>Run history</h2>
        {runs.isPending && <Loading label="Loading run history" />}
        {runs.isError && <ErrorState error={runs.error} />}
        {runs.isSuccess && runs.data.items.length === 0 && (
          <p className="muted">Nothing has been published yet.</p>
        )}
        {runs.isSuccess && runs.data.items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>When</th><th>Status</th><th>Shows</th><th>Episodes</th><th></th>
              </tr>
            </thead>
            <tbody>
              {runs.data.items.map((run, index) => (
                <tr key={run.id}>
                  <td>{timestamp(run.started_at)}</td>
                  <td>
                    <span className={`badge badge-${run.status === "success" ? "published" : "draft"}`}>
                      {run.status === "no_change" ? "no change" : run.status}
                    </span>
                  </td>
                  <td>{run.counts?.shows ?? ""}</td>
                  <td>{run.counts?.episodes ?? ""}</td>
                  <td>
                    {isAdmin && run.status === "success" && index > 0 && (
                      <button
                        disabled={rollback.isPending}
                        onClick={() => rollback.mutate(run.id)}
                      >
                        Make this live again
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {rollback.isSuccess && (
          <p className="note note-ok small">
            The catalogue now serves the run from {timestamp(rollback.data.started_at)}.
          </p>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Route and verify manually, including the role gate**

Add `<Route path="/publish" element={<PublishPage />} />`.

Sign in as `editor@peblo.test`. Expected: the publish button disabled with the explanation about administrators. Sign in as `admin@peblo.test`. Expected: enabled, and clicking it reports counts. Click again immediately. Expected: the message saying nothing had changed. Then set a published episode's duration to empty via the API and reload. Expected: the button disables and names that episode.

- [ ] **Step 3: Typecheck, lint, commit**

```bash
cd cms && npx tsc --noEmit && npm run lint
git add cms && git commit -m "feat(cms): publish page with blocking reasons, history and rollback"
```

---

### Task 6: Viewer scaffold, catalogue context, art component

**Files:**
- Create: the whole `viewer/` scaffold, `viewer/src/api/catalog.ts`, `viewer/src/catalog/CatalogContext.tsx`, `viewer/src/components/Art.tsx`, `viewer/src/components/Icon.tsx`, `viewer/src/styles.css`, `viewer/src/App.tsx`, `viewer/src/main.tsx`

**Interfaces:**
- Produces: types `Catalog`, `CatalogShow`, `CatalogEpisode`; `fetchCatalog()`, `searchCatalog(params)`; `useCatalog()` returning `{ status, catalog, error, retry }`; `<Art src alt ratio className?/>`

- [ ] **Step 1: Scaffold**

```bash
npm create vite@latest viewer -- --template react-ts
cd viewer && npm install && npm install react-router-dom && npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks
```

Set port 5174 in `viewer/vite.config.ts`, same shape as Task 1 step 2.

- [ ] **Step 2: Write `viewer/src/api/catalog.ts`**

This file is the reason the viewer cannot call an admin endpoint. There is no token, no auth header, and no admin path anywhere in it.

```ts
const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type Artwork = Partial<Record<"poster" | "banner" | "thumbnail", string>>;

export type CatalogEpisode = {
  content_group: string;
  episode_number: number;
  title: string;
  duration_seconds: number | null;
  languages: string[];
  artwork: Artwork;
};

export type CatalogSeason = { season_number: number; episodes: CatalogEpisode[] };

export type CatalogShow = {
  slug: string;
  title: string;
  synopsis: string;
  categories: string[];
  languages: string[];
  artwork: Artwork;
  trailers: CatalogEpisode[];
  seasons: CatalogSeason[];
};

export type Catalog = {
  version: number;
  run_id: string;
  generated_at: string;
  hero: { slug: string } | null;
  sections: { key: string; shows: CatalogShow[] }[];
};

export type SearchResult = {
  match: "show" | "episode" | "category";
  show: CatalogShow & { section: string };
  episode: (CatalogEpisode & { season_number: number }) | null;
};

async function readJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.errors?.[0]?.message ?? "We could not load the catalogue. Please try again.",
    );
  }
  return (await response.json()) as T;
}

export function fetchCatalog(): Promise<Catalog> {
  return readJson<Catalog>("/catalog");
}

export function searchCatalog(params: {
  q?: string;
  category?: string;
  language?: string;
  section?: string;
}): Promise<{ total: number; results: SearchResult[] }> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  return readJson(`/catalog/search?${search.toString()}`);
}
```

- [ ] **Step 3: Write `viewer/src/catalog/CatalogContext.tsx`**

One immutable document per session, so a fetch plus context is the whole of the state management. No query library, deliberately.

```tsx
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { type Catalog, fetchCatalog } from "../api/catalog";

type State =
  | { status: "loading"; catalog: null; error: null }
  | { status: "ready"; catalog: Catalog; error: null }
  | { status: "error"; catalog: null; error: string };

const CatalogContext = createContext<(State & { retry: () => void }) | null>(null);

export function CatalogProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading", catalog: null, error: null });
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading", catalog: null, error: null });
    fetchCatalog()
      .then((catalog) => {
        if (!cancelled) setState({ status: "ready", catalog, error: null });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ status: "error", catalog: null, error: error.message });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return (
    <CatalogContext.Provider value={{ ...state, retry }}>{children}</CatalogContext.Provider>
  );
}

export function useCatalog() {
  const value = useContext(CatalogContext);
  if (!value) throw new Error("useCatalog must be used inside CatalogProvider");
  return value;
}
```

- [ ] **Step 4: Write `viewer/src/styles.css`**

```css
@import url("https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&display=swap");

:root {
  --shell: oklch(0.16 0.01 260);
  --surface: oklch(0.21 0.015 260);
  --surface-2: oklch(0.26 0.018 260);
  --text: oklch(0.96 0.005 260);
  --text-muted: oklch(0.74 0.012 260);
  --accent: oklch(0.78 0.16 65);
  --accent-ink: oklch(0.2 0.04 65);

  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px;
  --s5: 24px; --s6: 40px; --s7: 64px;
  --radius: 12px;
  --radius-sm: 8px;
  --ease: cubic-bezier(0.23, 1, 0.32, 1);

  --display: "Baloo 2", system-ui, sans-serif;
  --body: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;

  color-scheme: dark;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--shell);
  color: var(--text);
  font: 16px/1.55 var(--body);
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3 { font-family: var(--display); line-height: 1.15; margin: 0; }
h1 { font-size: clamp(28px, 5vw, 52px); letter-spacing: -0.02em; text-wrap: balance; }
h2 { font-size: clamp(19px, 2.2vw, 24px); }
h3 { font-size: 17px; }

a { color: inherit; text-decoration: none; }

button {
  font: inherit;
  cursor: pointer;
  border: 0;
  border-radius: 999px;
  padding: 12px var(--s5);
  min-height: 44px;
  background: var(--accent);
  color: var(--accent-ink);
  font-weight: 700;
  transition: transform 150ms var(--ease), filter 150ms var(--ease);
}
button:hover { filter: brightness(1.07); }
button:active { transform: scale(0.97); }

:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 3px;
  border-radius: var(--radius-sm);
}

.shell { max-width: 1400px; margin: 0 auto; padding: 0 var(--s5); }
.muted { color: var(--text-muted); }
.stack > * + * { margin-top: var(--s4); }
.row-flex { display: flex; gap: var(--s3); align-items: center; flex-wrap: wrap; }

/* Reserve space before the image lands, so nothing on the page moves. */
.art {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--surface);
}
.art::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 37%, var(--surface) 63%);
  background-size: 400% 100%;
  animation: shimmer 1.4s infinite linear;
}
.art.is-loaded::after { display: none; }
.art img {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 250ms var(--ease);
}
.art.is-loaded img { opacity: 1; }
@keyframes shimmer { to { background-position: -135% 0; } }

.chip {
  display: inline-block;
  font-size: 13px;
  font-weight: 600;
  padding: 5px var(--s3);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text);
}
.chip-accent { background: var(--accent); color: var(--accent-ink); }

.scroller {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(150px, 168px);
  gap: var(--s4);
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  padding-bottom: var(--s3);
  scrollbar-width: thin;
}
.scroller > * { scroll-snap-align: start; }

input, select {
  font: inherit;
  min-height: 44px;
  padding: 10px var(--s4);
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-2);
  background: var(--surface);
  color: var(--text);
}
input::placeholder { color: var(--text-muted); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Write `viewer/src/components/Art.tsx`**

This is the whole answer to "stay pleasant when images are slow": space reserved by aspect ratio, a shimmer behind, a fade in, and a graceful fallback when there is no image at all.

```tsx
import { useState } from "react";

export function Art({
  src,
  alt,
  ratio,
  sizes,
}: {
  src: string | undefined;
  alt: string;
  ratio: string;
  sizes?: string;
}) {
  const [loaded, setLoaded] = useState(false);

  if (!src) {
    return (
      <div className="art is-loaded" style={{ aspectRatio: ratio, display: "grid", placeItems: "center" }}>
        <span className="muted" style={{ fontSize: 13 }}>
          {alt}
        </span>
      </div>
    );
  }

  return (
    <div className={`art${loaded ? " is-loaded" : ""}`} style={{ aspectRatio: ratio }}>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        sizes={sizes}
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(true)}
      />
    </div>
  );
}
```

- [ ] **Step 6: Write `viewer/src/App.tsx` and `main.tsx`**

```tsx
import { Link, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { CatalogProvider } from "./catalog/CatalogContext";
import { HomePage } from "./pages/HomePage";
import { SearchPage } from "./pages/SearchPage";
import { ShowPage } from "./pages/ShowPage";

export default function App() {
  return (
    <CatalogProvider>
      <Router>
        <header style={{ padding: "var(--s4) 0" }}>
          <div className="shell row-flex">
            <Link to="/" style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 22 }}>
              Peblo TV
            </Link>
            <nav style={{ marginLeft: "auto" }}>
              <Link to="/search" className="chip">
                Search
              </Link>
            </nav>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/show/:slug" element={<ShowPage />} />
        </Routes>
      </Router>
    </CatalogProvider>
  );
}
```

`main.tsx` is identical in shape to the CMS one from Task 1 step 9, importing `./styles.css`.

- [ ] **Step 7: Typecheck, lint, commit**

Pages do not exist yet, so create them as one-line stubs returning `null` first, then:

```bash
cd viewer && npx tsc --noEmit && npm run lint
git add viewer && git commit -m "feat(viewer): scaffold, catalogue context, slow-image art component"
```

---

### Task 7: Viewer home, hero and rows

**Files:**
- Create: `viewer/src/components/Hero.tsx`, `viewer/src/components/PosterCard.tsx`, `viewer/src/components/Row.tsx`, `viewer/src/components/Empty.tsx`, `viewer/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: `useCatalog`, `Art`
- Produces: `<Hero show/>`, `<PosterCard show/>`, `<Row title shows/>`, `<Empty title message/>`

- [ ] **Step 1: Write `viewer/src/components/PosterCard.tsx`**

Poster for rows, per the artwork-per-surface rule. Hover changes colour and shadow only, never size, so the row does not jitter.

```tsx
import { Link } from "react-router-dom";
import type { CatalogShow } from "../api/catalog";
import { Art } from "./Art";

export function PosterCard({ show }: { show: CatalogShow }) {
  return (
    <Link to={`/show/${show.slug}`} style={{ display: "block" }}>
      <Art src={show.artwork.poster} alt={show.title} ratio="2 / 3" sizes="168px" />
      <h3 style={{ marginTop: "var(--s2)", fontSize: 15 }}>{show.title}</h3>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {show.languages.map((l) => (l === "en" ? "English" : "Hindi")).join(" and ")}
      </p>
    </Link>
  );
}
```

- [ ] **Step 2: Write `viewer/src/components/Row.tsx`**

Native scroll snap. No carousel library, and arrow keys work because the container is focusable and horizontal scrolling is the browser's own behaviour.

```tsx
import type { CatalogShow } from "../api/catalog";
import { PosterCard } from "./PosterCard";

const TITLES: Record<string, string> = {
  featured: "Featured",
  series: "Series",
  minisodes: "Minisodes",
  songs: "Songs",
};

export function Row({ sectionKey, shows }: { sectionKey: string; shows: CatalogShow[] }) {
  if (shows.length === 0) return null;
  const heading = TITLES[sectionKey] ?? sectionKey;
  return (
    <section style={{ marginTop: "var(--s6)" }}>
      <h2 style={{ marginBottom: "var(--s3)" }}>{heading}</h2>
      <div
        className="scroller"
        tabIndex={0}
        role="group"
        aria-label={`${heading} shows, scroll horizontally`}
      >
        {shows.map((show) => (
          <PosterCard key={show.slug} show={show} />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Write `viewer/src/components/Hero.tsx`**

Banner artwork, per the artwork-per-surface rule. Synopsis capped so the hero never grows past the fold.

```tsx
import { Link } from "react-router-dom";
import type { CatalogShow } from "../api/catalog";
import { Art } from "./Art";

function capWords(text: string, max: number): string {
  const words = text.split(/\s+/);
  return words.length <= max ? text : `${words.slice(0, max).join(" ")}...`;
}

export function Hero({ show }: { show: CatalogShow }) {
  return (
    <section style={{ position: "relative", borderRadius: "var(--radius)", overflow: "hidden" }}>
      <Art src={show.artwork.banner} alt={show.title} ratio="16 / 9" sizes="100vw" />
      <div
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          padding: "var(--s6)",
          background:
            "linear-gradient(to top, oklch(0.16 0.01 260 / 0.94) 12%, oklch(0.16 0.01 260 / 0.55) 46%, transparent 78%)",
        }}
      >
        <h1 style={{ maxWidth: "16ch" }}>{show.title}</h1>
        <p className="muted" style={{ maxWidth: "52ch", marginTop: "var(--s3)" }}>
          {capWords(show.synopsis, 20)}
        </p>
        <div className="row-flex" style={{ marginTop: "var(--s4)" }}>
          <Link to={`/show/${show.slug}`}>
            <button>Start watching</button>
          </Link>
          {show.trailers.length > 0 && <span className="chip">Trailer available</span>}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Write `viewer/src/components/Empty.tsx`**

```tsx
export function Empty({ title, message }: { title: string; message: string }) {
  return (
    <div style={{ padding: "var(--s7) var(--s5)", textAlign: "center" }}>
      <h2>{title}</h2>
      <p className="muted" style={{ maxWidth: "44ch", margin: "var(--s3) auto 0" }}>
        {message}
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Write `viewer/src/pages/HomePage.tsx`**

```tsx
import { useCatalog } from "../catalog/CatalogContext";
import { Empty } from "../components/Empty";
import { Hero } from "../components/Hero";
import { Row } from "../components/Row";

export function HomePage() {
  const { status, catalog, error, retry } = useCatalog();

  if (status === "loading") {
    return (
      <div className="shell">
        <div className="art" style={{ aspectRatio: "16 / 9" }} />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="shell">
        <Empty title="We could not load Peblo TV" message={error} />
        <div style={{ textAlign: "center" }}>
          <button onClick={retry}>Try again</button>
        </div>
      </div>
    );
  }

  const shows = catalog.sections.flatMap((s) => s.shows);
  if (shows.length === 0) {
    return (
      <div className="shell">
        <Empty
          title="Nothing to watch yet"
          message="New shows are on their way. Check back in a little while."
        />
      </div>
    );
  }

  const hero = shows.find((s) => s.slug === catalog.hero?.slug) ?? shows[0];

  return (
    <div className="shell" style={{ paddingBottom: "var(--s7)" }}>
      <Hero show={hero} />
      {catalog.sections.map((section) => (
        <Row key={section.key} sectionKey={section.key} shows={section.shows} />
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Verify manually, including the slow case**

Open `http://localhost:5174`. Expected: hero showing Moti's Many Lives with the banner, then four rows using posters.

Open dev tools, throttle the network to "Slow 3G", reload. Expected: every image slot holds its space with a shimmer, nothing on the page jumps as images arrive, and the layout is fully usable before any image has loaded.

- [ ] **Step 7: Typecheck, lint, commit**

```bash
cd viewer && npx tsc --noEmit && npm run lint
git add viewer && git commit -m "feat(viewer): home with banner hero and poster rows"
```

---

### Task 8: Viewer search and filters

**Files:**
- Create: `viewer/src/pages/SearchPage.tsx`

**Interfaces:**
- Consumes: `searchCatalog`, `Art`, `Empty`

- [ ] **Step 1: Write `viewer/src/pages/SearchPage.tsx`**

Search is server side. The comment says why, because the brief penalises browser-side search over the whole catalogue with no comment on scale.

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type SearchResult, searchCatalog } from "../api/catalog";
import { Art } from "../components/Art";
import { Empty } from "../components/Empty";

const CATEGORIES = [
  "adventure", "folk", "friendship", "india", "language", "learning", "maths",
  "music", "nature", "reading", "science", "singalong", "stories", "travel", "values",
];

export function SearchPage() {
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [language, setLanguage] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Server side on purpose. Shipping the whole catalogue to the browser to
    // filter it there works at this size and stops working the moment the
    // catalogue outgrows a phone's memory budget.
    const timer = setTimeout(() => {
      setBusy(true);
      setError(null);
      searchCatalog({ q: text, category, language })
        .then((data) => setResults(data.results))
        .catch((caught: Error) => setError(caught.message))
        .finally(() => setBusy(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [text, category, language]);

  return (
    <div className="shell stack" style={{ paddingBottom: "var(--s7)" }}>
      <h1>Search</h1>

      <div className="row-flex">
        <input
          type="search"
          placeholder="Try a show, an episode, or a topic"
          aria-label="Search shows and episodes"
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ flex: 1, minWidth: 220 }}
        />
        <select
          aria-label="Filter by category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All topics</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="Filter by language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="">Any language</option>
          <option value="en">English</option>
          <option value="hi">Hindi</option>
        </select>
      </div>

      <p className="muted" aria-live="polite" style={{ fontSize: 14 }}>
        {busy ? "Searching" : results ? `${results.length} results` : ""}
      </p>

      {error && <Empty title="Search is unavailable" message={error} />}

      {!error && results?.length === 0 && (
        <Empty
          title="Nothing matched that"
          message={
            language || category
              ? "Try clearing the language or topic filter, or searching for something shorter."
              : "Try a shorter word, or browse the rows on the home page."
          }
        />
      )}

      {!error && results && results.length > 0 && (
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            display: "grid",
            gap: "var(--s4)",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          }}
        >
          {results.map((result, index) => (
            <li key={`${result.show.slug}-${result.episode?.content_group ?? index}`}>
              <Link to={`/show/${result.show.slug}`} className="row-flex" style={{ gap: "var(--s3)" }}>
                <div style={{ width: 120, flexShrink: 0 }}>
                  <Art
                    src={result.episode ? result.episode.artwork.thumbnail : result.show.artwork.poster}
                    alt={result.episode?.title ?? result.show.title}
                    ratio={result.episode ? "16 / 9" : "2 / 3"}
                    sizes="120px"
                  />
                </div>
                <div>
                  <h3>{result.episode?.title ?? result.show.title}</h3>
                  {/* Episode titles repeat across shows, so a result without
                      its show name is not actionable. */}
                  <p className="muted" style={{ margin: "2px 0 0", fontSize: 14 }}>
                    {result.episode
                      ? `${result.show.title}, season ${result.episode.season_number}, episode ${result.episode.episode_number}`
                      : result.show.categories.join(", ")}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify manually**

Search `The Lost Kite`. Expected: multiple results, each naming its show, season and episode. Set language to Hindi and section-free. Expected: fewer results, and `peblo-songs-lyrical` disappears because it is English only. Search `zzzz`. Expected: the written empty state, not a blank page.

- [ ] **Step 3: Typecheck, lint, commit**

```bash
cd viewer && npx tsc --noEmit && npm run lint
git add viewer && git commit -m "feat(viewer): server-side search with composing filters"
```

---

### Task 9: Viewer show detail, and the copy audit

**Files:**
- Create: `viewer/src/pages/ShowPage.tsx`
- Create: `viewer/scripts/check-copy.mjs`, `cms/scripts/check-copy.mjs`

**Interfaces:**
- Consumes: `useCatalog`, `Art`, `Empty`

- [ ] **Step 1: Write `viewer/src/pages/ShowPage.tsx`**

Season 0 never appears as a season. Trailers get their own strip. Language options for a grouped episode render as chips.

```tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { Art } from "../components/Art";
import { Empty } from "../components/Empty";
import { useCatalog } from "../catalog/CatalogContext";

const LANGUAGE_NAMES: Record<string, string> = { en: "English", hi: "Hindi" };

function minutes(seconds: number | null): string {
  if (!seconds) return "";
  return `${Math.round(seconds / 60)} min`;
}

export function ShowPage() {
  const slug = useParams().slug;
  const { status, catalog, error } = useCatalog();
  const [season, setSeason] = useState<number | null>(null);

  if (status === "loading") {
    return <div className="shell"><div className="art" style={{ aspectRatio: "16 / 9" }} /></div>;
  }
  if (status === "error") {
    return <div className="shell"><Empty title="We could not load this show" message={error} /></div>;
  }

  const show = catalog.sections.flatMap((s) => s.shows).find((s) => s.slug === slug);
  if (!show) {
    return (
      <div className="shell">
        <Empty
          title="We could not find that show"
          message="It may have been taken down. Try the home page to see what is available."
        />
      </div>
    );
  }

  // Season 0 is reserved for trailers, so it is never offered as a season.
  const seasons = show.seasons;
  const active = seasons.find((s) => s.season_number === season) ?? seasons[0];

  return (
    <div className="shell stack" style={{ paddingBottom: "var(--s7)" }}>
      <section style={{ position: "relative", borderRadius: "var(--radius)", overflow: "hidden" }}>
        <Art src={show.artwork.banner} alt={show.title} ratio="16 / 9" sizes="100vw" />
        <div
          style={{
            position: "absolute", inset: 0, zIndex: 2, display: "flex",
            flexDirection: "column", justifyContent: "flex-end", padding: "var(--s6)",
            background:
              "linear-gradient(to top, oklch(0.16 0.01 260 / 0.94) 14%, transparent 74%)",
          }}
        >
          <h1>{show.title}</h1>
          <p className="muted" style={{ maxWidth: "60ch", marginTop: "var(--s3)" }}>
            {show.synopsis}
          </p>
          <div className="row-flex" style={{ marginTop: "var(--s4)" }}>
            {show.categories.map((c) => (
              <span key={c} className="chip">{c}</span>
            ))}
            {show.languages.map((l) => (
              <span key={l} className="chip chip-accent">{LANGUAGE_NAMES[l] ?? l}</span>
            ))}
          </div>
        </div>
      </section>

      {show.trailers.length > 0 && (
        <section>
          <h2>Trailer</h2>
          <div className="row-flex" style={{ marginTop: "var(--s3)", alignItems: "flex-start" }}>
            {show.trailers.map((trailer) => (
              <div key={trailer.content_group} style={{ width: 240 }}>
                <Art src={trailer.artwork.thumbnail} alt={trailer.title} ratio="16 / 9" sizes="240px" />
                <h3 style={{ marginTop: "var(--s2)" }}>{trailer.title}</h3>
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                  {minutes(trailer.duration_seconds)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="row-flex">
          <h2>Episodes</h2>
          {seasons.length > 1 && (
            <select
              aria-label="Choose a season"
              value={active.season_number}
              onChange={(e) => setSeason(Number(e.target.value))}
            >
              {seasons.map((s) => (
                <option key={s.season_number} value={s.season_number}>
                  Season {s.season_number}
                </option>
              ))}
            </select>
          )}
        </div>

        <ul
          style={{
            listStyle: "none", padding: 0, marginTop: "var(--s4)",
            display: "grid", gap: "var(--s4)",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          }}
        >
          {active.episodes.map((episode) => (
            <li key={episode.content_group} className="row-flex" style={{ alignItems: "flex-start" }}>
              <div style={{ width: 132, flexShrink: 0 }}>
                <Art src={episode.artwork.thumbnail} alt={episode.title} ratio="16 / 9" sizes="132px" />
              </div>
              <div>
                <h3>
                  {episode.episode_number}. {episode.title}
                </h3>
                <p className="muted" style={{ margin: "2px 0 var(--s2)", fontSize: 14 }}>
                  {minutes(episode.duration_seconds)}
                </p>
                <div className="row-flex" style={{ gap: "var(--s1)" }}>
                  {episode.languages.map((l) => (
                    <span key={l} className="chip" style={{ fontSize: 12 }}>
                      {LANGUAGE_NAMES[l] ?? l}
                    </span>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Write the copy audit script**

Create the same file in both `cms/scripts/check-copy.mjs` and `viewer/scripts/check-copy.mjs`. It catches the two things most likely to slip through a manual review.

```js
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const EM_DASH = /—/;
const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const failures = [];
for (const file of walk("src").filter((f) => /\.(tsx?|css)$/.test(f))) {
  readFileSync(file, "utf8")
    .split("\n")
    .forEach((line, index) => {
      if (EM_DASH.test(line)) failures.push(`${file}:${index + 1} em dash`);
      if (EMOJI.test(line)) failures.push(`${file}:${index + 1} emoji`);
    });
}

if (failures.length > 0) {
  console.error("Copy audit failed:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("Copy audit passed.");
```

Add to both `package.json` files:

```json
"scripts": { "check:copy": "node scripts/check-copy.mjs" }
```

- [ ] **Step 3: Run the audit and the typecheck in both apps**

```bash
cd cms && npm run check:copy && npx tsc --noEmit && npm run lint
cd ../viewer && npm run check:copy && npx tsc --noEmit && npm run lint
```
Expected: both pass. Fix any em dash or emoji it finds rather than relaxing the rule.

- [ ] **Step 4: Verify the whole viewer manually**

Open `motis-many-lives`. Expected: no "Season 0" in the season control, a separate Trailer strip, and episode 2 showing both English and Hindi chips because those two rows collapsed into one entry. Open `curious-cubs`. Expected: English chips only. Open `discover-india-with-moti`. Expected: episode 4 is absent, because it was downgraded at import.

Resize to 375px. Expected: no horizontal page scroll, rows still scroll inside themselves, and every tap target at least 44px.

- [ ] **Step 5: Commit**

```bash
git add cms viewer && git commit -m "feat(viewer): show detail with trailers, seasons and language chips"
```

---

## Frontends acceptance checklist

- [ ] `tsc --noEmit`, `eslint`, and `check:copy` pass in both apps
- [ ] Signing into the CMS as an editor shows the publish button disabled with a written reason
- [ ] Uploading `poster_wrong_ratio.jpg` shows a sentence about rotation, not a status code
- [ ] The CMS handles loading, empty, error and permission denied on every async surface
- [ ] The viewer never sends an `Authorization` header. Confirm in the network tab
- [ ] `grep -r "admin" viewer/src` returns nothing
- [ ] On Slow 3G the viewer has no layout shift as images arrive
- [ ] Season 0 does not appear as a season anywhere in the viewer
- [ ] Every interactive element shows a focus ring when tabbed to
