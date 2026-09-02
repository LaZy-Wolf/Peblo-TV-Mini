/** Drawn icons, one consistent stroke weight. No emoji anywhere. */
type IconName = "play" | "search" | "back" | "arrow" | "ticket" | "empty";

const PATHS: Record<IconName, string> = {
  play: "M7 4.5v15l13-7.5z",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35",
  back: "M15 19l-7-7 7-7",
  arrow: "M5 12h14M13 5l7 7-7 7",
  ticket: "M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2 2 2 0 0 0 0 4 2 2 0 0 0 0 4 2 2 0 0 1-2 2H6a2 2 0 0 1-2-2 2 2 0 0 0 0-4 2 2 0 0 0 0-4zM12 7v2M12 15v2",
  empty: "M4 7h16M4 12h10M4 17h7",
};

export function Icon({
  name,
  size = 18,
  label,
  filled = false,
}: {
  name: IconName;
  size?: number;
  label?: string;
  filled?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill={filled ? "currentColor" : "none"}
      stroke={filled ? "none" : "currentColor"}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ flexShrink: 0 }}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/** The wordmark's arch, echoing the jharokha the poster cards are cut from. */
export function ArchMark({ size = 26 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 26" width={size} height={size} aria-hidden="true">
      <path
        d="M3 25V12a9 9 0 0 1 18 0v13"
        fill="var(--amber)"
        stroke="var(--ink)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="11" r="2.4" fill="var(--ink)" />
    </svg>
  );
}
