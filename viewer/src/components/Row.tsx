import { useRef } from "react";
import type { CatalogShow } from "../api/catalog";
import { Icon } from "./Icon";
import { PosterCard } from "./PosterCard";
import { Reveal } from "./Reveal";

const TITLES: Record<string, string> = {
  featured: "Featured",
  series: "Series",
  minisodes: "Minisodes",
  songs: "Songs",
};

/**
 * Native CSS scroll snap, no carousel library. The container is focusable
 * so arrow keys scroll it using the browser's own behaviour, and the two
 * buttons are there for a small hand on a tablet that will not think to
 * swipe a row.
 */
export function Row({
  sectionKey,
  shows,
  index = 0,
}: {
  sectionKey: string;
  shows: CatalogShow[];
  index?: number;
}) {
  const scroller = useRef<HTMLDivElement>(null);

  if (shows.length === 0) return null;
  const heading = TITLES[sectionKey] ?? sectionKey;

  function nudge(direction: 1 | -1) {
    scroller.current?.scrollBy({ left: direction * 420, behavior: "smooth" });
  }

  return (
    <Reveal
      as="section"
      delay={index * 90}
      className={`band band-${index % 4}`}
    >
      <div className="shell">
        <div className="row-head">
          <h2>{heading}</h2>
          <span className="row-rule" aria-hidden="true" />
          {shows.length > 3 && (
            <span className="row-flex" style={{ gap: "var(--s2)" }}>
              <button
                className="btn-quiet"
                style={{ minHeight: 40, padding: "0 var(--s3)" }}
                onClick={() => nudge(-1)}
                aria-label={`Scroll ${heading} left`}
              >
                <Icon name="back" size={16} />
              </button>
              <button
                className="btn-quiet"
                style={{ minHeight: 40, padding: "0 var(--s3)" }}
                onClick={() => nudge(1)}
                aria-label={`Scroll ${heading} right`}
              >
                <Icon name="arrow" size={16} />
              </button>
            </span>
          )}
        </div>

        <div
          ref={scroller}
          className="scroller"
          tabIndex={0}
          role="group"
          aria-label={`${heading}, scroll sideways for more`}
        >
          {shows.map((show) => (
            <PosterCard key={show.slug} show={show} />
          ))}
        </div>
      </div>
    </Reveal>
  );
}
