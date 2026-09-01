import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { useUploadArtwork } from "../api/hooks";

/** The required size is shown before upload, not after a failure.
 *  Errors come from the server, so the client cannot disagree with it about
 *  what is valid. */
const SPECS = {
  poster: {
    label: "Poster",
    size: "600 by 900",
    note: "Tall. Used for the cards in browse rows.",
    ratio: "2 / 3",
    width: 180,
  },
  banner: {
    label: "Banner",
    size: "1280 by 720",
    note: "Wide. Used for the big featured image.",
    ratio: "16 / 9",
    width: 288,
  },
  thumbnail: {
    label: "Thumbnail",
    size: "640 by 360",
    note: "Wide. Used in episode lists.",
    ratio: "16 / 9",
    width: 288,
  },
} as const;

export function ArtworkSlot({
  kind,
  showId,
  episodeId,
  currentUrl,
}: {
  kind: keyof typeof SPECS;
  showId?: number;
  episodeId?: number;
  currentUrl?: string;
}) {
  const spec = SPECS[kind];
  const upload = useUploadArtwork();
  const [preview, setPreview] = useState<string | null>(null);

  // Object URLs leak if this is forgotten.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function onPick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    upload.mutate({ kind, file, showId, episodeId });
    event.target.value = "";
  }

  const shown = preview ?? currentUrl;
  const errors = upload.error instanceof ApiError ? upload.error.errors : [];
  const inputId = `artwork-${kind}-${showId ?? "x"}-${episodeId ?? "x"}`;

  return (
    <div className="stack-tight" style={{ width: spec.width, maxWidth: "100%" }}>
      <div>
        <label htmlFor={inputId}>{spec.label}</label>
        <p className="muted small" style={{ margin: 0 }}>
          {spec.size} pixels. {spec.note}
        </p>
      </div>

      <div className="slot-frame" style={{ aspectRatio: spec.ratio }}>
        {shown ? (
          <img src={shown} alt={`${spec.label} preview`} />
        ) : (
          <span className="muted small">No {spec.label.toLowerCase()} yet</span>
        )}
      </div>

      <input id={inputId} type="file" accept="image/*" onChange={onPick} />

      {upload.isPending && <p className="muted small">Checking and uploading</p>}

      {upload.isSuccess && errors.length === 0 && (
        <p className="note note-ok small">
          Uploaded at {upload.data.width} by {upload.data.height} pixels.
        </p>
      )}

      {errors.map((e) => (
        <p key={e.code} className="note note-error small" role="alert">
          {e.message}
        </p>
      ))}
    </div>
  );
}
