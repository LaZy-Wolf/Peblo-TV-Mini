import { useState } from "react";

/**
 * Reserves its space by aspect ratio before the image arrives, sweeps a
 * paper-toned shimmer meanwhile, then fades in. Zero layout shift on a
 * slow connection.
 *
 * `arch` cuts the frame as a jharokha dome for poster surfaces. Episode
 * thumbnails stay rectangular, because cropping a 16:9 still into an arch
 * would eat the part of the frame that tells you what the episode is.
 */
export function Art({
  src,
  alt,
  ratio,
  sizes,
  arch = false,
}: {
  src: string | undefined;
  alt: string;
  ratio: string;
  sizes?: string;
  arch?: boolean;
}) {
  const [settled, setSettled] = useState(false);
  const shape = arch ? " art-arch" : "";

  if (!src) {
    return (
      <div
        className={`art is-loaded art-fallback${shape}`}
        style={{ aspectRatio: ratio }}
      >
        <span>{alt}</span>
      </div>
    );
  }

  return (
    <div
      className={`art${shape}${settled ? " is-loaded" : ""}`}
      style={{ aspectRatio: ratio }}
    >
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
