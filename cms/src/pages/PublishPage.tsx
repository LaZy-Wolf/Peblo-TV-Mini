import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { usePublish, useRollback, useRuns, useValidationReport } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { ErrorState, Loading } from "../components/States";

function timestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "";
}

function issueLink(entityType: string, entityId: number | null) {
  if (entityId === null) return null;
  if (entityType === "show") return `/shows/${entityId}`;
  if (entityType === "episode") return `/episodes/${entityId}`;
  return null;
}

export function PublishPage() {
  const { isAdmin } = useAuth();
  const report = useValidationReport();
  const runs = useRuns();
  const publish = usePublish();
  const rollback = useRollback();

  const publishError = publish.error instanceof ApiError ? publish.error : null;
  const liveRunId = runs.data?.items.find((r) => r.status === "success")?.id;

  return (
    <div className="stack">
      <h1>Publish</h1>

      {report.isPending && <Loading label="Checking the catalogue" />}
      {report.isError && <ErrorState error={report.error} onRetry={() => report.refetch()} />}

      {report.isSuccess && (
        <section className="panel stack">
          <h2>Ready to publish</h2>

          {report.data.can_publish ? (
            <p className="note note-ok">
              <Icon name="check" /> Nothing is blocking a publish.
              {report.data.warning_count > 0 &&
                ` ${report.data.warning_count} warnings below are worth a look but will not stop you.`}
            </p>
          ) : (
            <div className="note note-error">
              <strong>
                <Icon name="alert" /> {report.data.blocking_count} problems must be fixed first
              </strong>
              <ul>
                {report.data.groups.flatMap((group) =>
                  group.blocking.map((issue) => {
                    const href = issueLink(issue.entity_type, issue.entity_id);
                    return (
                      <li key={`${group.show_slug}-${issue.code}-${issue.entity_id}`}>
                        <strong>{group.show_title}</strong>, {issue.entity_label}:{" "}
                        {issue.message}{" "}
                        {href && <Link to={href}>Open and fix this</Link>}
                      </li>
                    );
                  }),
                )}
              </ul>
            </div>
          )}

          {!isAdmin && (
            <p className="note note-warn">
              <Icon name="block" /> You are signed in as an editor. Publishing is restricted to
              administrators. Everything above is still worth fixing, then ask an administrator
              to publish.
            </p>
          )}

          <div className="row">
            <button
              className="button-primary"
              disabled={!isAdmin || !report.data.can_publish || publish.isPending}
              onClick={() => publish.mutate()}
            >
              {publish.isPending ? "Publishing" : "Publish catalogue"}
            </button>

            {publish.isSuccess && !publishError && (
              <span className="note note-ok small">
                {publish.data.status === "no_change"
                  ? "Nothing had changed, so the live catalogue was left exactly as it was."
                  : `Published. ${publish.data.counts?.shows} shows and ${publish.data.counts?.episodes} episodes are now live.`}
              </span>
            )}
          </div>

          {publishError && (
            <div className="note note-error" role="alert">
              {publishError.errors.map((e) => (
                <p key={e.code} style={{ margin: 0 }}>
                  {e.message}
                </p>
              ))}
            </div>
          )}
        </section>
      )}

      {report.isSuccess && report.data.import_problems.length > 0 && (
        <section className="panel stack">
          <h2>Data import problems</h2>
          <p className="muted small" style={{ margin: 0 }}>
            These rows arrived from a bulk import in a state our rules do not allow. They are
            listed here so you can decide what to do, rather than being silently dropped.
          </p>
          <ul className="stack-tight" style={{ margin: 0, paddingLeft: "var(--s5)" }}>
            {report.data.import_problems.map((problem) => (
              <li key={problem.id}>
                <span className="badge badge-draft">
                  {problem.action === "rejected" ? "Not imported" : "Imported as draft"}
                </span>{" "}
                {problem.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      {report.isSuccess && report.data.warning_count > 0 && (
        <section className="panel stack">
          <h2>Warnings</h2>
          <ul className="stack-tight" style={{ margin: 0, paddingLeft: "var(--s5)" }}>
            {report.data.groups.flatMap((group) =>
              group.warnings.map((issue) => (
                <li key={`${group.show_slug}-${issue.code}-${issue.entity_label}`}>
                  <strong>{group.show_title}</strong>, {issue.entity_label}: {issue.message}{" "}
                  <span className="muted small">{issue.fix_hint}</span>
                </li>
              )),
            )}
          </ul>
        </section>
      )}

      <section className="panel panel-flush">
        <h2>Run history</h2>

        {runs.isPending && <Loading label="Loading run history" />}
        {runs.isError && <ErrorState error={runs.error} />}

        {runs.isSuccess && runs.data.items.length === 0 && (
          <p className="muted" style={{ padding: "0 var(--s5) var(--s5)" }}>
            Nothing has been published yet.
          </p>
        )}

        {runs.isSuccess && runs.data.items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Status</th>
                <th>Shows</th>
                <th>Episodes</th>
                <th>By</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.data.items.map((run) => (
                <tr key={run.id}>
                  <td>{timestamp(run.started_at)}</td>
                  <td>
                    <span className={`badge badge-${run.status}`}>
                      {run.status === "no_change" ? "no change" : run.status}
                    </span>
                    {run.id === liveRunId && (
                      <span className="muted small"> currently live</span>
                    )}
                  </td>
                  <td>{run.counts?.shows ?? ""}</td>
                  <td>{run.counts?.episodes ?? ""}</td>
                  <td className="muted small">{run.started_by ?? "system"}</td>
                  <td>
                    {isAdmin && run.status === "success" && run.id !== liveRunId && (
                      <button
                        className="button-small"
                        disabled={rollback.isPending}
                        onClick={() => rollback.mutate(run.id)}
                      >
                        Make this live again
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {rollback.isSuccess && (
          <p className="note note-ok small" style={{ margin: "var(--s4) var(--s5) var(--s5)" }}>
            The catalogue now serves the run from {timestamp(rollback.data.started_at)}.
          </p>
        )}
        {rollback.error instanceof ApiError && (
          <p
            className="note note-error small"
            style={{ margin: "var(--s4) var(--s5) var(--s5)" }}
            role="alert"
          >
            {rollback.error.message}
          </p>
        )}
      </section>
    </div>
  );
}
