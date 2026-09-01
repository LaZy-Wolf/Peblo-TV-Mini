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
    <div style={{ padding: "var(--s7) var(--s5)", textAlign: "center" }}>
      <h2>{title}</h2>
      <p className="muted" style={{ maxWidth: "44ch", margin: "var(--s3) auto 0" }}>
        {message}
      </p>
      {action && <div style={{ marginTop: "var(--s5)" }}>{action}</div>}
    </div>
  );
}
