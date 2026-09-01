import { useCatalog } from "../catalog/CatalogContext";
import { Empty } from "../components/Empty";
import { Hero } from "../components/Hero";
import { Row } from "../components/Row";

export function HomePage() {
  const { status, catalog, error, retry } = useCatalog();

  if (status === "loading") {
    return (
      <div className="shell">
        <div className="art" style={{ aspectRatio: "16 / 9" }} />
        <div className="scroller" style={{ marginTop: "var(--s6)" }}>
          {[0, 1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="art" style={{ aspectRatio: "2 / 3" }} />
          ))}
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="shell">
        <Empty
          title="We could not load Peblo TV"
          message={error}
          action={<button onClick={retry}>Try again</button>}
        />
      </div>
    );
  }

  const shows = catalog.sections.flatMap((s) => s.shows);
  if (shows.length === 0) {
    return (
      <div className="shell">
        <Empty
          title="Nothing to watch yet"
          message="New shows are on their way. Check back in a little while."
        />
      </div>
    );
  }

  const hero = shows.find((s) => s.slug === catalog.hero?.slug) ?? shows[0];

  return (
    <div className="shell" style={{ paddingBottom: "var(--s7)" }}>
      <Hero show={hero} />
      {catalog.sections.map((section) => (
        <Row key={section.key} sectionKey={section.key} shows={section.shows} />
      ))}
    </div>
  );
}
