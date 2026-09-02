import { useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Doodles } from "../components/Doodles";
import { ArchMark } from "../components/Icon";

/** The two seeded accounts. Filling the form from a tap saves a reviewer
 *  copying credentials out of a README, and makes the difference between
 *  the roles obvious before anyone signs in. The server still decides what
 *  each role may do; this only types for you. */
const ACCOUNTS = [
  {
    key: "editor",
    label: "Editor",
    blurb: "Add and edit content",
    email: "editor@peblo.test",
    password: "editor-dev-password",
  },
  {
    key: "admin",
    label: "Administrator",
    blurb: "Everything, plus publish",
    email: "admin@peblo.test",
    password: "admin-dev-password",
  },
];

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function fill(account: (typeof ACCOUNTS)[number]) {
    setEmail(account.email);
    setPassword(account.password);
    setPicked(account.key);
    setError(null);
  }

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
    <main className="login">
      <section className="login-art">
        <Doodles />
        <span className="login-badge">
          <ArchMark size={30} />
        </span>
        <h1>Everything that reaches Peblo TV starts here.</h1>
        <p>
          Add shows, upload artwork, check what is blocking a release, and publish when it is
          ready.
        </p>
      </section>

      <section className="login-form">
        <div className="login-card stack">
          <div>
            <h2>Sign in</h2>
            <p className="muted small" style={{ margin: "var(--s1) 0 0" }}>
              Use one of the demo accounts, or type your own.
            </p>
          </div>

          <div className="role-grid">
            {ACCOUNTS.map((account) => (
              <button
                key={account.key}
                type="button"
                className="role"
                aria-pressed={picked === account.key}
                onClick={() => fill(account)}
              >
                <strong>{account.label}</strong>
                <span>{account.blurb}</span>
              </button>
            ))}
          </div>

          <form onSubmit={onSubmit} className="stack">
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
                placeholder="you@peblo.test"
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

          <p className="login-foot muted">
            Peblo TV is at{" "}
            <a href="http://localhost:5174" target="_blank" rel="noreferrer">
              localhost:5174
            </a>
          </p>
        </div>
      </section>
    </main>
  );
}
