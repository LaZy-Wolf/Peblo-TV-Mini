import { ApiError } from "../api/client";
import { Icon } from "./Icon";

/** Every async surface in the CMS uses these, so the four states are handled
 *  by construction rather than by remembering to handle them. */

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="panel stack-tight" role="status" aria-live="polite">
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
      <ul className="stack-tight" style={{ margin: 0, paddingLeft: "var(--s5)" }}>
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
      <p className="muted" style={{ margin: 0 }}>
        {message}
      </p>
      {action}
    </div>
  );
}
