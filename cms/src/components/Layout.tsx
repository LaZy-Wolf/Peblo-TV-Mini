import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { email, role, logout } = useAuth();
  return (
    <>
      <header className="site-header">
        <div className="row shell">
          <strong style={{ marginRight: "var(--s5)" }}>Peblo CMS</strong>
          <nav className="row grow" style={{ gap: "var(--s5)" }}>
            <NavLink to="/shows" className={({ isActive }) => (isActive ? "active" : "")}>
              Shows
            </NavLink>
            <NavLink to="/publish" className={({ isActive }) => (isActive ? "active" : "")}>
              Publish
            </NavLink>
          </nav>
          <span className="muted small">
            {email} ({role})
          </span>
          <button className="button-small" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="shell">
        <Outlet />
      </main>
    </>
  );
}
