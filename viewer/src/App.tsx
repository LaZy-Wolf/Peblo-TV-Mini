import { Link, NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { CatalogProvider } from "./catalog/CatalogContext";
import { HomePage } from "./pages/HomePage";
import { SearchPage } from "./pages/SearchPage";
import { ShowPage } from "./pages/ShowPage";

export default function App() {
  return (
    <CatalogProvider>
      <Router>
        <header className="site-header">
          <div className="shell row-flex">
            <Link
              to="/"
              style={{ fontFamily: "var(--display)", fontWeight: 700, fontSize: 22 }}
            >
              Peblo TV
            </Link>
            <nav style={{ marginLeft: "auto" }}>
              <NavLink to="/search" className="chip">
                Search
              </NavLink>
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
