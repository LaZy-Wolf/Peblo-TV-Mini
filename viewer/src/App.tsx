import { useEffect, useState } from "react";
import { Link, NavLink, Route, BrowserRouter as Router, Routes, useLocation } from "react-router-dom";
import { CatalogProvider } from "./catalog/CatalogContext";
import { ArchMark, Icon } from "./components/Icon";
import { HomePage } from "./pages/HomePage";
import { SearchPage } from "./pages/SearchPage";
import { ShowPage } from "./pages/ShowPage";

function Header() {
  const [scrolled, setScrolled] = useState(false);

  // The header only grows a rule once the page has moved, so a page at
  // rest has no line drawn across it for no reason.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="site-header" data-scrolled={scrolled}>
      <div className="shell row-flex">
        <Link to="/" className="wordmark">
          <ArchMark />
          Peblo TV
        </Link>
        <nav style={{ marginLeft: "auto" }}>
          <NavLink to="/search" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <Icon name="search" size={16} />
            Search
          </NavLink>
        </nav>
      </div>
    </header>
  );
}

/** Keyed on the path so each route replays its entrance. */
function Pages() {
  const location = useLocation();
  return (
    <div className="page" key={location.pathname}>
      <Routes location={location}>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/show/:slug" element={<ShowPage />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <CatalogProvider>
      <Router>
        <Header />
        <Pages />
        <footer className="shell muted" style={{ padding: "var(--s7) 0 var(--s6)", fontSize: 14 }}>
          Peblo TV. Stories for small people.
        </footer>
      </Router>
    </CatalogProvider>
  );
}
