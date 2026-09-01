import { Link } from "react-router-dom";
import type { CatalogShow } from "../api/catalog";
import { Art } from "./Art";

const LANGUAGE_NAMES: Record<string, string> = { en: "English", hi: "Hindi" };

/** Rows use poster artwork, per the artwork-per-surface rule. */
export function PosterCard({ show }: { show: CatalogShow }) {
  return (
    <Link to={`/show/${show.slug}`} className="card">
      <Art src={show.artwork.poster} alt={show.title} ratio="2 / 3" sizes="168px" />
      <h3 style={{ marginTop: "var(--s2)", fontSize: 15 }}>{show.title}</h3>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {show.languages.map((l) => LANGUAGE_NAMES[l] ?? l).join(" and ")}
      </p>
    </Link>
  );
}
