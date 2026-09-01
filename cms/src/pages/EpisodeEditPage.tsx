import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import type { EpisodeDetail } from "../api/hooks";
import { useEpisode, useUpdateEpisode } from "../api/hooks";
import { ArtworkSlot } from "../components/ArtworkSlot";
import { Field } from "../components/Field";
import { ErrorState, Loading } from "../components/States";

export function EpisodeEditPage() {
  const id = Number(useParams().id);
  const episode = useEpisode(id);

  if (episode.isPending) return <Loading label="Loading episode" />;
  if (episode.isError) {
    return <ErrorState error={episode.error} onRetry={() => episode.refetch()} />;
  }

  const isTrailer = episode.data.season_number === 0;

  return (
    <div className="stack">
      <div className="row">
        <Link to={`/shows/${episode.data.show_id}`} className="small">
          Back to {episode.data.show_title}
        </Link>
      </div>

      <div className="row">
        <h1 className="grow">
          Season {episode.data.season_number}, episode {episode.data.episode_number}:{" "}
          {episode.data.title}
        </h1>
        <span className={`badge badge-${episode.data.status}`}>{episode.data.status}</span>
      </div>

      {isTrailer && (
        <p className="note note-warn">
          This is a trailer. Season 0 is reserved for trailers, so this does not appear as a
          season on Peblo TV. It needs a thumbnail and nothing else.
        </p>
      )}

      {/* Keyed on the record, so the form initialises from real data and
          navigating to another episode resets it, with no syncing effect. */}
      <EpisodeForm key={episode.data.id} episode={episode.data} />

      <section className="panel stack">
        <h2>Thumbnail</h2>
        <ArtworkSlot
          kind="thumbnail"
          episodeId={id}
          currentUrl={episode.data.artwork?.thumbnail}
        />
      </section>
    </div>
  );
}

function EpisodeForm({ episode }: { episode: EpisodeDetail }) {
  const update = useUpdateEpisode(episode.id);
  const [form, setForm] = useState({
    title: episode.title,
    duration_seconds: episode.duration_seconds?.toString() ?? "",
    language: episode.language,
    content_group: episode.content_group,
  });

  const error = update.error instanceof ApiError ? update.error : null;
  const isPublished = episode.status === "published";

  return (
    <section className="panel stack">
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
          label="Duration in seconds"
          htmlFor="duration"
          hint="How long the episode runs. Required before it can be published."
          errors={error?.forField("duration_seconds")}
        >
          <input
            id="duration"
            type="number"
            min={1}
            value={form.duration_seconds}
            onChange={(e) => setForm({ ...form, duration_seconds: e.target.value })}
          />
        </Field>

        <Field label="Language" htmlFor="language" errors={error?.forField("language")}>
          <select
            id="language"
            value={form.language}
            onChange={(e) => setForm({ ...form, language: e.target.value })}
          >
            <option value="en">English</option>
            <option value="hi">Hindi</option>
          </select>
        </Field>

        <Field
          label="Content group"
          htmlFor="group"
          hint={
            "Episodes sharing a content group are the same episode in different languages. " +
            "Viewers see one entry with a language choice. Each language may appear once " +
            "per group."
          }
          errors={error?.forField("content_group")}
        >
          <input
            id="group"
            value={form.content_group}
            onChange={(e) => setForm({ ...form, content_group: e.target.value })}
          />
        </Field>

        <div className="row">
          <button
            className="button-primary"
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                title: form.title,
                duration_seconds: form.duration_seconds
                  ? Number(form.duration_seconds)
                  : null,
                language: form.language,
                content_group: form.content_group,
              })
            }
          >
            {update.isPending ? "Saving" : "Save changes"}
          </button>

          <button
            disabled={update.isPending}
            onClick={() => update.mutate({ status: isPublished ? "draft" : "published" })}
          >
            {isPublished ? "Move back to draft" : "Publish this episode"}
          </button>

          {update.isSuccess && !error && <span className="note note-ok small">Saved</span>}
        </div>
    </section>
  );
}
