import { Link } from "react-router-dom";
import type { CatalogShow } from "../api/catalog";
import { Art } from "./Art";
import { Icon } from "./Icon";

/**
 * The hero is a lit stage: copy on the left, the show's banner raised on
 * the right as the topmost sheet of paper. Banner artwork, per the
 * artwork-per-surface rule.
 *
 * The copy staggers in on mount. That is the one authored moment on the
 * page; everything else reveals quietly on scroll.
 */
function capWords(text: string, max: number): string {
  const words = text.trim().split(/\s+/);
  return words.length <= max ? text : `${words.slice(0, max).join(" ")}...`;
}

export function Hero({ show }: { show: CatalogShow }) {
  const steps = [0, 90, 180, 270];

  return (
    <section className="hero">
      <div className="hero-copy">
        <span
          data-reveal=""
          className="is-in chip chip-solid"
          style={{ ["--reveal-delay" as string]: `${steps[0]}ms` }}
        >
          <Icon name="ticket" size={14} />
          Now showing
        </span>

        <h1
          data-reveal=""
          className="is-in"
          style={{
            marginTop: "var(--s4)",
            ["--reveal-delay" as string]: `${steps[1]}ms`,
          }}
        >
          {show.title}
        </h1>

        <p
          data-reveal=""
          className="is-in muted"
          style={{
            marginTop: "var(--s3)",
            fontSize: 17,
            ["--reveal-delay" as string]: `${steps[2]}ms`,
          }}
        >
          {capWords(show.synopsis, 20)}
        </p>

        <div
          data-reveal=""
          className="is-in row-flex"
          style={{
            marginTop: "var(--s5)",
            ["--reveal-delay" as string]: `${steps[3]}ms`,
          }}
        >
          <Link to={`/show/${show.slug}`} className="btn">
            <Icon name="play" size={17} filled />
            Start watching
          </Link>
          {show.trailers.length > 0 && <span className="chip">Trailer inside</span>}
          {show.languages.map((l) => (
            <span key={l} className="chip chip-lang">
              {l === "en" ? "English" : "Hindi"}
            </span>
          ))}
        </div>
      </div>

      <div className="hero-art">
        <Art src={show.artwork.banner} alt={show.title} ratio="16 / 9" sizes="44vw" />
      </div>
    </section>
  );
}
