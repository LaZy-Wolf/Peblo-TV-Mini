import { useCatalog } from "../catalog/CatalogContext";
import { Empty } from "../components/Empty";
import { Hero } from "../components/Hero";
import { Row } from "../components/Row";

function HomeSkeleton() {
  return (
    <div className="shell">
      <div
        className="art"
        style={{ aspectRatio: "21 / 9", marginTop: "var(--s5)", borderRadius: "var(--r-lg)" }}
      />
      <div className="scroller" style={{ marginTop: "var(--s7)" }}>
        {[0, 1, 2, 3, 4, 5, 6].map((n) => (
          <div key={n} className="art art-arch" style={{ aspectRatio: "2 / 3" }} />
        ))}
      </div>
    </div>
  );
}

export function HomePage() {
  const { status, catalog, error, retry } = useCatalog();

  if (status === "loading") return <HomeSkeleton />;

  if (status === "error") {
    return (
      <div className="shell">
        <Empty
          title="We could not load Peblo TV"
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
    <div className="shell" style={{ paddingBottom: "var(--s6)" }}>
      <Hero show={hero} />
      {catalog.sections.map((section, index) => (
        <Row key={section.key} sectionKey={section.key} shows={section.shows} index={index} />
      ))}
    </div>
  );
}
