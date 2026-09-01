import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import type { ShowDetail } from "../api/hooks";
import { useEpisodes, useShow, useUpdateShow } from "../api/hooks";
import { ArtworkSlot } from "../components/ArtworkSlot";
import { Field } from "../components/Field";
import { ErrorState, Loading } from "../components/States";

const SECTIONS = ["featured", "series", "minisodes", "songs"];
const CATEGORIES = [
  "adventure",
  "folk",
  "friendship",
  "india",
  "language",
  "learning",
  "maths",
  "music",
  "nature",
  "reading",
  "science",
  "singalong",
  "stories",
  "travel",
  "values",
];

function duration(seconds: number | null) {
  if (!seconds) return null;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
}

export function ShowEditPage() {
  const id = Number(useParams().id);
  const show = useShow(id);
  const episodes = useEpisodes(id);

  if (show.isPending) return <Loading label="Loading show" />;
  if (show.isError) return <ErrorState error={show.error} onRetry={() => show.refetch()} />;

  return (
    <div className="stack">
      <div className="row">
        <Link to="/shows" className="small">
          Back to shows
        </Link>
      </div>

      <div className="row">
        <h1 className="grow">{show.data.title}</h1>
        <span className={`badge badge-${show.data.status}`}>{show.data.status}</span>
      </div>

      {/* Keyed on the record, so the form's initial state comes from real data
          and navigating to another show resets it, with no syncing effect. */}
      <ShowDetailsForm key={show.data.id} show={show.data} />

      <section className="panel stack">
        <h2>Artwork</h2>
        <div className="row row-top" style={{ gap: "var(--s5)" }}>
          <ArtworkSlot kind="poster" showId={id} currentUrl={show.data.artwork?.poster} />
          <ArtworkSlot kind="banner" showId={id} currentUrl={show.data.artwork?.banner} />
          <ArtworkSlot kind="thumbnail" showId={id} currentUrl={show.data.artwork?.thumbnail} />
        </div>
      </section>

      <section className="panel panel-flush">
        <h2>Episodes</h2>
        {episodes.isPending && <Loading label="Loading episodes" />}
        {episodes.isError && <ErrorState error={episodes.error} />}
        {episodes.isSuccess && episodes.data.total === 0 && (
          <p className="muted" style={{ padding: "0 var(--s5) var(--s5)" }}>
            This show has no episodes yet.
          </p>
        )}
        {episodes.isSuccess && episodes.data.total > 0 && (
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>Title</th>
                <th>Language</th>
                <th>Duration</th>
                <th>Status</th>
                <th>Content group</th>
              </tr>
            </thead>
            <tbody>
              {episodes.data.items.map((e) => (
                <tr key={e.id}>
                  <td>{e.episode_number}</td>
                  <td>
                    <Link to={`/episodes/${e.id}`}>{e.title}</Link>
                  </td>
                  <td>{e.language}</td>
                  <td>
                    {duration(e.duration_seconds) ?? (
                      <span className="muted small">Not set</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge badge-${e.status}`}>{e.status}</span>
                  </td>
                  <td className="muted small">{e.content_group}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function ShowDetailsForm({ show }: { show: ShowDetail }) {
  const update = useUpdateShow(show.id);
  const [form, setForm] = useState({
    title: show.title,
    synopsis: show.synopsis,
    section: show.section ?? "",
    categories: show.categories,
  });

  const error = update.error instanceof ApiError ? update.error : null;
  const isPublished = show.status === "published";

  return (
    <>
      <section className="panel stack">
        <h2>Details</h2>

        {error?.general.map((e) => (
          <p key={e.code} className="note note-error" role="alert">
            {e.message}
          </p>
        ))}

        <Field label="Title" htmlFor="title" errors={error?.forField("title")}>
          <input
            id="title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </Field>

        <Field
          label="Section"
          htmlFor="section"
          hint="Which row this show appears in on Peblo TV. A show cannot be published without one."
          errors={error?.forField("section")}
        >
          <select
            id="section"
            value={form.section}
            onChange={(e) => setForm({ ...form, section: e.target.value })}
          >
            <option value="">Not set</option>
            {SECTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Synopsis" htmlFor="synopsis" errors={error?.forField("synopsis")}>
          <textarea
            id="synopsis"
            rows={3}
            value={form.synopsis}
            onChange={(e) => setForm({ ...form, synopsis: e.target.value })}
          />
        </Field>

        <Field
          label="Categories"
          htmlFor="categories"
          hint="Used by the topic filter on Peblo TV."
          errors={error?.forField("categories")}
        >
          <div className="row" id="categories" style={{ gap: "var(--s3)" }}>
            {CATEGORIES.map((c) => (
              <label
                key={c}
                className="row small"
                style={{ fontWeight: 400, gap: "var(--s1)", marginBottom: 0, width: "auto" }}
              >
                <input
                  type="checkbox"
                  checked={form.categories.includes(c)}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      categories: e.target.checked
                        ? [...form.categories, c]
                        : form.categories.filter((x) => x !== c),
                    })
                  }
                />
                {c}
              </label>
            ))}
          </div>
        </Field>

        <div className="row">
          <button
            className="button-primary"
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                title: form.title,
                synopsis: form.synopsis,
                section: form.section || null,
                categories: form.categories,
              })
            }
          >
            {update.isPending ? "Saving" : "Save changes"}
          </button>

          <button
            disabled={update.isPending}
            onClick={() => update.mutate({ status: isPublished ? "draft" : "published" })}
          >
            {isPublished ? "Move back to draft" : "Publish this show"}
          </button>

          {update.isSuccess && !error && <span className="note note-ok small">Saved</span>}
        </div>
      </section>
    </>
  );
}
