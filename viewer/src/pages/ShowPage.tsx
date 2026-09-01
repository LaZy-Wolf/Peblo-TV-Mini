import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Art } from "../components/Art";
import { Empty } from "../components/Empty";
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
        <div className="art" style={{ aspectRatio: "16 / 9" }} />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="shell">
        <Empty
          title="We could not load this show"
          message={error}
          action={<button onClick={retry}>Try again</button>}
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
          message="It may have been taken down. Try the home page to see what is available."
          action={
            <Link to="/">
              <button>Back to Peblo TV</button>
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
    <div className="shell stack" style={{ paddingBottom: "var(--s7)" }}>
      <section style={{ position: "relative", borderRadius: "var(--radius)", overflow: "hidden" }}>
        <Art src={show.artwork.banner} alt={show.title} ratio="16 / 9" sizes="100vw" />
        <div className="hero-overlay">
          <h1>{show.title}</h1>
          <p className="muted" style={{ maxWidth: "60ch", marginTop: "var(--s3)" }}>
            {show.synopsis}
          </p>
          <div className="row-flex" style={{ marginTop: "var(--s4)" }}>
            {show.categories.map((c) => (
              <span key={c} className="chip">
                {c}
              </span>
            ))}
            {show.languages.map((l) => (
              <span key={l} className="chip chip-accent">
                {LANGUAGE_NAMES[l] ?? l}
              </span>
            ))}
          </div>
        </div>
      </section>

      {show.trailers.length > 0 && (
        <section>
          <h2>Trailer</h2>
          <div className="row-flex" style={{ marginTop: "var(--s3)", alignItems: "flex-start" }}>
            {show.trailers.map((trailer) => (
              <div key={trailer.content_group} style={{ width: 240 }}>
                <Art
                  src={trailer.artwork.thumbnail}
                  alt={trailer.title}
                  ratio="16 / 9"
                  sizes="240px"
                />
                <h3 style={{ marginTop: "var(--s2)" }}>{trailer.title}</h3>
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                  {minutes(trailer.duration_seconds)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="row-flex">
          <h2>Episodes</h2>
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

        <ul className="grid-cards" style={{ marginTop: "var(--s4)" }}>
          {active.episodes.map((episode) => (
            <li key={episode.content_group} className="row-flex" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
              <div style={{ width: 132, flexShrink: 0 }}>
                <Art
                  src={episode.artwork.thumbnail}
                  alt={episode.title}
                  ratio="16 / 9"
                  sizes="132px"
                />
              </div>
              <div>
                <h3>
                  {episode.episode_number}. {episode.title}
                </h3>
                <p className="muted" style={{ margin: "2px 0 var(--s2)", fontSize: 14 }}>
                  {minutes(episode.duration_seconds)}
                </p>
                {/* Language options for a grouped episode. */}
                <div className="row-flex" style={{ gap: "var(--s1)" }}>
                  {episode.languages.map((l) => (
                    <span key={l} className="chip" style={{ fontSize: 12 }}>
                      {LANGUAGE_NAMES[l] ?? l}
                    </span>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
