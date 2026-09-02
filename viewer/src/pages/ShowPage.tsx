import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Art } from "../components/Art";
import { Empty } from "../components/Empty";
import { Icon } from "../components/Icon";
import { Reveal } from "../components/Reveal";
import { useCatalog } from "../catalog/CatalogContext";

const LANGUAGE_NAMES: Record<string, string> = { en: "English", hi: "Hindi" };

function minutes(seconds: number | null): string {
  if (!seconds) return "";
  return `${Math.round(seconds / 60)} min`;
}

export function ShowPage() {
  const slug = useParams().slug;
  const { status, catalog, error, retry } = useCatalog();
  const [season, setSeason] = useState<number | null>(null);

  if (status === "loading") {
    return (
      <div className="shell">
        <div className="art" style={{ aspectRatio: "21 / 9", marginTop: "var(--s5)" }} />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="shell">
        <Empty
          title="We could not load this show"
          message={error}
          action={
            <button onClick={retry} className="btn">
              Try again
            </button>
          }
        />
      </div>
    );
  }

  const show = catalog.sections.flatMap((s) => s.shows).find((s) => s.slug === slug);
  if (!show) {
    return (
      <div className="shell">
        <Empty
          title="We could not find that show"
          message="It may have been taken down. Try the home page to see what is playing."
          action={
            <Link to="/" className="btn">
              Back to Peblo TV
            </Link>
          }
        />
      </div>
    );
  }

  // Season 0 is reserved for trailers, so the catalogue never puts it in
  // seasons and it is never offered here as one.
  const seasons = show.seasons;
  const active = seasons.find((s) => s.season_number === season) ?? seasons[0];

  return (
    <div className="shell" style={{ paddingBottom: "var(--s6)" }}>
      <Link
        to="/"
        className="chip"
        style={{ marginTop: "var(--s4)", display: "inline-flex" }}
      >
        <Icon name="back" size={14} />
        All shows
      </Link>

      <section className="hero" style={{ marginTop: "var(--s4)" }}>
        <div className="hero-copy">
          <h1>{show.title}</h1>
          <p className="muted" style={{ marginTop: "var(--s3)", fontSize: 17 }}>
            {show.synopsis}
          </p>
          <div className="row-flex" style={{ marginTop: "var(--s5)" }}>
            {show.categories.map((c) => (
              <span key={c} className="chip">
                {c}
              </span>
            ))}
            {show.languages.map((l) => (
              <span key={l} className="chip chip-lang">
                {LANGUAGE_NAMES[l] ?? l}
              </span>
            ))}
          </div>
        </div>
        <div className="hero-art">
          <Art src={show.artwork.banner} alt={show.title} ratio="16 / 9" sizes="44vw" />
        </div>
      </section>

      {show.trailers.length > 0 && (
        <Reveal as="section" style={{ marginTop: "var(--s7)" }}>
          <div className="row-head">
            <h2>Trailer</h2>
            <span className="row-rule" aria-hidden="true" />
          </div>
          <div className="row-flex" style={{ alignItems: "flex-start" }}>
            {show.trailers.map((trailer) => (
              <div key={trailer.content_group} style={{ width: 260 }} className="card">
                <Art
                  src={trailer.artwork.thumbnail}
                  alt={trailer.title}
                  ratio="16 / 9"
                  sizes="260px"
                />
                <h3>{trailer.title}</h3>
                <p className="card-meta tnum">{minutes(trailer.duration_seconds)}</p>
              </div>
            ))}
          </div>
        </Reveal>
      )}

      <Reveal as="section" style={{ marginTop: "var(--s7)" }}>
        <div className="row-head">
          <h2>Episodes</h2>
          <span className="row-rule" aria-hidden="true" />
          {seasons.length > 1 && (
            <select
              aria-label="Choose a season"
              value={active.season_number}
              onChange={(e) => setSeason(Number(e.target.value))}
            >
              {seasons.map((s) => (
                <option key={s.season_number} value={s.season_number}>
                  Season {s.season_number}
                </option>
              ))}
            </select>
          )}
        </div>

        <ul className="ep-grid">
          {active.episodes.map((episode) => (
            <li key={episode.content_group} className="ep">
              <div style={{ width: 132, flexShrink: 0 }}>
                <Art
                  src={episode.artwork.thumbnail}
                  alt={episode.title}
                  ratio="16 / 9"
                  sizes="132px"
                />
              </div>
              <div style={{ minWidth: 0 }}>
                <span className="ep-num">Episode {episode.episode_number}</span>
                <h3 style={{ marginTop: 2 }}>{episode.title}</h3>
                <p className="card-meta tnum">{minutes(episode.duration_seconds)}</p>
                {/* Language options for a grouped episode. */}
                <div className="row-flex" style={{ gap: 6, marginTop: "var(--s2)" }}>
                  {episode.languages.map((l) => (
                    <span key={l} className="chip chip-lang" style={{ fontSize: 12 }}>
                      {LANGUAGE_NAMES[l] ?? l}
                    </span>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Reveal>
    </div>
  );
}
