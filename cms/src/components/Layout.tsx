import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ArchMark } from "./Icon";

export function Layout() {
  const { email, role, logout } = useAuth();
  return (
    <>
      <header className="site-header">
        <div className="row shell">
          <span className="brand" style={{ marginRight: "var(--s5)" }}>
            <ArchMark size={22} />
            Peblo CMS
          </span>
          <nav className="row grow" style={{ gap: "var(--s2)" }}>
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
