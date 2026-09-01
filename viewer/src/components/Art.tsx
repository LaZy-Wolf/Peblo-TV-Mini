import { useState } from "react";

/**
 * Reserves its space by aspect ratio before the image arrives, shows a
 * shimmer meanwhile, then fades in. Zero layout shift on a slow connection,
 * and a readable fallback when a show has no artwork at all.
 */
export function Art({
  src,
  alt,
  ratio,
  sizes,
}: {
  src: string | undefined;
  alt: string;
  ratio: string;
  sizes?: string;
}) {
  const [settled, setSettled] = useState(false);

  if (!src) {
    return (
      <div className="art is-loaded art-fallback" style={{ aspectRatio: ratio }}>
        <span>{alt}</span>
      </div>
    );
  }

  return (
    <div className={`art${settled ? " is-loaded" : ""}`} style={{ aspectRatio: ratio }}>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        sizes={sizes}
        onLoad={() => setSettled(true)}
        onError={() => setSettled(true)}
      />
    </div>
  );
}
