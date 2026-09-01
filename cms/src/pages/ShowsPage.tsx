import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useShows } from "../api/hooks";
import { Empty, ErrorState, Loading } from "../components/States";
import { Pagination } from "../components/Pagination";

const SECTIONS = ["featured", "series", "minisodes", "songs"];
const PAGE_SIZE = 20;

export function ShowsPage() {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [section, setSection] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  // Debounced, so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(text);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [text]);

  const query = useShows({ q, section, status, page, page_size: PAGE_SIZE });
  const hasFilters = Boolean(q || section || status);

  return (
    <div className="stack">
      <h1>Shows</h1>

      <div className="panel row row-top">
        <div className="grow" style={{ minWidth: 220 }}>
          <label htmlFor="q">Search</label>
          <input
            id="q"
            type="search"
            placeholder="Show title or web address"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="section">Section</label>
          <select
            id="section"
            value={section}
            onChange={(e) => {
              setSection(e.target.value);
              // Landing on page 4 of a one page result is the classic filter bug.
              setPage(1);
            }}
          >
            <option value="">All sections</option>
            {SECTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="status">Status</label>
          <select
            id="status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
          </select>
        </div>
      </div>

      {query.isPending && <Loading label="Loading shows" />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}

      {query.isSuccess && query.data.total === 0 && (
        <Empty
          title="No shows match those filters"
          message={
            hasFilters
              ? "Try clearing the section or status filter, or searching for a different title."
              : "There are no shows yet. Once content is imported it will appear here."
          }
        />
      )}

      {query.isSuccess && query.data.total > 0 && (
        <div className="panel panel-flush">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Section</th>
                <th>Status</th>
                <th>Categories</th>
                <th>Web address</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((show) => (
                <tr key={show.id}>
                  <td>
                    <Link to={`/shows/${show.id}`}>{show.title}</Link>
                  </td>
                  <td>
                    {show.section ?? <span className="muted small">Not set</span>}
                  </td>
                  <td>
                    <span className={`badge badge-${show.status}`}>{show.status}</span>
                  </td>
                  <td className="muted small">{show.categories.join(", ") || "None"}</td>
                  <td className="muted small">{show.slug}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination
            page={query.data.page}
            pageSize={query.data.page_size}
            total={query.data.total}
            onPage={setPage}
          />
        </div>
      )}
    </div>
  );
}
