import type { CatalogShow } from "../api/catalog";
import { PosterCard } from "./PosterCard";

const TITLES: Record<string, string> = {
  featured: "Featured",
  series: "Series",
  minisodes: "Minisodes",
  songs: "Songs",
};

/** Native CSS scroll snap, no carousel library. The container is focusable,
 *  so arrow keys scroll it using the browser's own behaviour. */
export function Row({ sectionKey, shows }: { sectionKey: string; shows: CatalogShow[] }) {
  if (shows.length === 0) return null;
  const heading = TITLES[sectionKey] ?? sectionKey;
  return (
    <section style={{ marginTop: "var(--s6)" }}>
      <h2 style={{ marginBottom: "var(--s3)" }}>{heading}</h2>
      <div
        className="scroller"
        tabIndex={0}
        role="group"
        aria-label={`${heading}, scroll sideways for more`}
      >
        {shows.map((show) => (
          <PosterCard key={show.slug} show={show} />
        ))}
      </div>
    </section>
  );
}
