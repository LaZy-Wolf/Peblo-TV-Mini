import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type SearchResult, searchCatalog } from "../api/catalog";
import { Art } from "../components/Art";
import { Empty } from "../components/Empty";
import { Icon } from "../components/Icon";
import { Reveal } from "../components/Reveal";

const CATEGORIES = [
  "adventure", "folk", "friendship", "india", "language", "learning", "maths",
  "music", "nature", "reading", "science", "singalong", "stories", "travel", "values",
];

export function SearchPage() {
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [language, setLanguage] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Server side on purpose. Shipping the whole catalogue to the browser
    // to filter it there works at this size and stops working the moment
    // the catalogue outgrows a phone's memory budget.
    const timer = setTimeout(() => {
      setBusy(true);
      setError(null);
      searchCatalog({ q: text, category, language })
        .then((data) => setResults(data.results))
        .catch((caught: Error) => setError(caught.message))
        .finally(() => setBusy(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [text, category, language]);

  const hasFilters = Boolean(category || language);

  return (
    <div className="shell" style={{ paddingBottom: "var(--s6)" }}>
      <div style={{ paddingTop: "var(--s6)" }}>
        <h1>What shall we watch?</h1>
      </div>

      <div className="row-flex" style={{ marginTop: "var(--s5)" }}>
        <span style={{ position: "relative", flex: 1, minWidth: 240, display: "flex" }}>
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              left: "var(--s4)",
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--ink-faint)",
              display: "flex",
            }}
          >
            <Icon name="search" size={17} />
          </span>
          <input
            type="search"
            placeholder="A show, an episode, or a topic"
            aria-label="Search shows and episodes"
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ flex: 1, paddingLeft: 46 }}
          />
        </span>
        <select
          aria-label="Filter by topic"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All topics</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="Filter by language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="">Any language</option>
          <option value="en">English</option>
          <option value="hi">Hindi</option>
        </select>
      </div>

      <p className="muted tnum" aria-live="polite" style={{ fontSize: 14, marginTop: "var(--s4)" }}>
        {busy ? "Looking" : results ? `${results.length} results` : ""}
      </p>

      {error && <Empty title="Search is unavailable" message={error} />}

      {!error && results?.length === 0 && (
        <Empty
          title="Nothing matched that"
          message={
            hasFilters
              ? "Try clearing the topic or language filter, or searching for something shorter."
              : "Try a shorter word, or browse the rows on the home page."
          }
        />
      )}

      {!error && results && results.length > 0 && (
        <ul className="ep-grid" style={{ marginTop: "var(--s4)" }}>
          {results.map((result, index) => (
            <Reveal
              as="li"
              key={`${result.show.slug}-${result.episode?.content_group ?? index}`}
              delay={Math.min(index, 8) * 45}
            >
              <Link to={`/show/${result.show.slug}`} className="ep card" style={{ width: "100%" }}>
                <div style={{ width: result.episode ? 132 : 92, flexShrink: 0 }}>
                  <Art
                    src={
                      result.episode
                        ? result.episode.artwork.thumbnail
                        : result.show.artwork.poster
                    }
                    alt={result.episode?.title ?? result.show.title}
                    ratio={result.episode ? "16 / 9" : "2 / 3"}
                    sizes="132px"
                    arch={!result.episode}
                  />
                </div>
                <div style={{ minWidth: 0 }}>
                  <h3>{result.episode?.title ?? result.show.title}</h3>
                  {/* Episode titles repeat across shows, so a result without
                      its show and position is not actionable. */}
                  <p className="card-meta">
                    {result.episode
                      ? `${result.show.title}, season ${result.episode.season_number}, episode ${result.episode.episode_number}`
                      : result.show.categories.join(", ")}
                  </p>
                  <div className="row-flex" style={{ gap: 6, marginTop: "var(--s2)" }}>
                    {(result.episode?.languages ?? result.show.languages).map((l) => (
                      <span key={l} className="chip chip-lang" style={{ fontSize: 12 }}>
                        {l === "en" ? "English" : "Hindi"}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>
            </Reveal>
          ))}
        </ul>
      )}
    </div>
  );
}
