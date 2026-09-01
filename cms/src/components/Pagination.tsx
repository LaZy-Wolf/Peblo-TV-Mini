export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="row" style={{ justifyContent: "space-between", padding: "var(--s3) var(--s5)" }}>
      <span className="muted small" aria-live="polite">
        Showing {from} to {to} of {total}
      </span>
      <div className="row">
        <button className="button-small" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Previous
        </button>
        <span className="small muted">
          Page {page} of {lastPage}
        </span>
        <button
          className="button-small"
          onClick={() => onPage(page + 1)}
          disabled={page >= lastPage}
        >
          Next
        </button>
      </div>
    </div>
  );
}
