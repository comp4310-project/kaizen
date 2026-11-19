// The loading, empty and error states every data view uses. See AGENTS.md, "States".
import type { ReactNode } from "react";
import { ApiError } from "./api";
import { useAuth } from "./auth";

/** "the model gave no usable reply" becomes "The model gave no usable reply." */
function sentence(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "";
  const first = trimmed[0].toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(first) ? first : `${first}.`;
}

/** What went wrong, in plain words, followed by the server's own reason when it gave one. */
export function describeError(error: unknown, role: string | undefined): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : String(error);
  switch (error.status) {
    case 0:
      return "The Kaizen API is not reachable. Start it from the backend folder with uvicorn kaizen.api.app:create_app --factory, then try again.";
    case 401:
      return "Your login has ended. Log in again.";
    case 403:
      return `Your role (${role ?? "unknown"}) cannot see or change this.`;
    case 404:
      return "Not found. It may have been removed, or it belongs to a unit you cannot see.";
    case 409:
      return `This cannot be done yet: ${error.message}.`;
    case 422:
      return `The server did not accept this: ${error.message}.`;
    // These come with a full sentence that says what to do, for example when the model
    // used for drafting is not running.
    case 502:
    case 503:
      return sentence(error.message) || "The server could not finish this. Try again.";
    default:
      return `Error ${error.status}: ${error.message}.`;
  }
}

/** Whether pressing the same button again could work. A 403, 404 or 422 will not change. */
export function canRetry(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  return error.status === 0 || error.status === 409 || error.status >= 500;
}

/**
 * Inline error for a view or an action. Announced to screen readers when it appears.
 * Pass `onRetry` where repeating the request could work; the button only shows for errors
 * that a retry can fix (no connection, a server or model failure).
 */
export function ErrorNotice({ error, onRetry, retryLabel = "Try again" }: {
  error: unknown;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  const { me } = useAuth();
  if (error === null || error === undefined) return null;
  const retry = onRetry && canRetry(error);
  return (
    <div className="notice notice-error" role="alert">
      <p>{describeError(error, me?.role)}</p>
      {retry && (
        <button type="button" className="btn btn-secondary btn-small" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

/** Says why a view is empty and how to fill it. */
export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

/**
 * Placeholder rows shaped like the real table. `columns` should match the real header so
 * the layout does not jump when the data arrives. Pass the class of numeric columns so
 * their bars sit on the right like the numbers will.
 */
export function SkeletonRows({ columns, rows = 6, optional = [] }: {
  columns: ("text" | "num" | "wide")[];
  rows?: number;
  /** Indexes of columns the real table marks `col-optional` (hidden on narrow screens). */
  optional?: number[];
}) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="skeleton-row" aria-hidden="true">
          {columns.map((kind, c) => (
            <td key={c} className={[kind === "num" ? "num" : "", optional.includes(c) ? "col-optional" : ""].join(" ").trim() || undefined}>
              <span className={`skeleton skeleton-${kind}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

/**
 * Placeholder blocks for lists. `card` gives each block the suggestion card's border, so
 * use it where cards will appear and leave it off for divided lists such as comments.
 */
export function SkeletonBlocks({ count = 3, label, card = false }: { count?: number; label: string; card?: boolean }) {
  return (
    <div role="status" aria-label={label} className={card ? "card-grid" : undefined}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={card ? "skeleton-block card" : "skeleton-block"} aria-hidden="true">
          <span className="skeleton skeleton-text" />
          <span className="skeleton skeleton-wide" />
          <span className="skeleton skeleton-wide" />
        </div>
      ))}
    </div>
  );
}
