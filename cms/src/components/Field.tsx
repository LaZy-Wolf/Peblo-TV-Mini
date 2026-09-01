import type { FieldError } from "../api/client";

export function Field({
  label,
  htmlFor,
  hint,
  errors,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  errors?: FieldError[];
  children: React.ReactNode;
}) {
  const hasErrors = Boolean(errors?.length);
  return (
    <div>
      <label htmlFor={htmlFor}>{label}</label>
      {hint && (
        <p id={`${htmlFor}-hint`} className="muted small" style={{ margin: "0 0 var(--s2)" }}>
          {hint}
        </p>
      )}
      {children}
      {hasErrors &&
        errors?.map((e) => (
          <p
            key={e.code}
            id={`${htmlFor}-error`}
            className="note note-error small"
            style={{ marginTop: "var(--s1)" }}
            role="alert"
          >
            {e.message}
          </p>
        ))}
    </div>
  );
}
