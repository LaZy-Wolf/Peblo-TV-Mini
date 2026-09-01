/** Inline SVG only. No emoji is ever used as an icon. */
type IconName = "check" | "alert" | "block" | "clock";

const PATHS: Record<IconName, string> = {
  check: "M20 6 9 17l-5-5",
  alert: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  block: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM5 5l14 14",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
};

export function Icon({ name, label }: { name: IconName; label?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      style={{ flexShrink: 0, verticalAlign: "-2px" }}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
