import { Icon } from "./Icon";

export function Empty({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="state">
      <span
        aria-hidden="true"
        style={{
          display: "inline-grid",
          placeItems: "center",
          width: 64,
          height: 64,
          borderRadius: "999px 999px 16px 16px",
          background: "var(--paper-raised)",
          boxShadow: "var(--lift-1)",
          color: "var(--ink-faint)",
          marginBottom: "var(--s4)",
        }}
      >
        <Icon name="empty" size={26} />
      </span>
      <h2>{title}</h2>
      <p className="muted">{message}</p>
      {action && <div style={{ marginTop: "var(--s5)" }}>{action}</div>}
    </div>
  );
}
