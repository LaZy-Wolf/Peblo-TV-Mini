import { Link } from "react-router-dom";
import type { CatalogShow } from "../api/catalog";
import { Art } from "./Art";

/** The hero uses banner artwork, per the artwork-per-surface rule. */
function capWords(text: string, max: number): string {
  const words = text.trim().split(/\s+/);
  return words.length <= max ? text : `${words.slice(0, max).join(" ")}...`;
}

export function Hero({ show }: { show: CatalogShow }) {
  return (
    <section style={{ position: "relative", borderRadius: "var(--radius)", overflow: "hidden" }}>
      <Art src={show.artwork.banner} alt={show.title} ratio="16 / 9" sizes="100vw" />
      <div className="hero-overlay">
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
