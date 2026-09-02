import { useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ArchMark } from "../components/Icon";

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
    <main className="login">
      <div className="login-card">
        <span className="login-mark">
          <ArchMark size={30} />
        </span>

        <h1>Peblo CMS</h1>
        <p className="muted" style={{ marginTop: "var(--s2)" }}>
          Sign in to manage shows, artwork and publishing.
        </p>

        <form onSubmit={onSubmit} className="stack" style={{ marginTop: "var(--s5)" }}>
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
      </div>

      <p className="login-foot muted">
        Peblo TV runs at{" "}
        <a href="http://localhost:5174" target="_blank" rel="noreferrer">
          localhost:5174
        </a>
      </p>
    </main>
  );
}
