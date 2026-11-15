// The loading, empty and error states every data view uses. See AGENTS.md, "States".
import type { ReactNode } from "react";
import { ApiError } from "./api";
import { useAuth } from "./auth";

/** What went wrong, in plain words, followed by the server's own reason when it gave one. */
export function describeError(error: unknown, role: string | undefined): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : String(error);
  switch (error.status) {
    case 0:
      return "Cannot reach the API. Check that uvicorn is running on port 8000.";
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
    case 502:
    case 503:
      return `The server could not finish this: ${error.message}.`;
    default:
      return `Error ${error.status}: ${error.message}.`;
  }
}

/** Inline error for a view or an action. Announced to screen readers when it appears. */
export function ErrorNotice({ error }: { error: unknown }) {
  const { me } = useAuth();
  if (error === null || error === undefined) return null;
  return (
    <p className="notice notice-error" role="alert">
      {describeError(error, me?.role)}
    </p>
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
export function SkeletonRows({ columns, rows = 6 }: { columns: ("text" | "num" | "wide")[]; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="skeleton-row" aria-hidden="true">
          {columns.map((kind, c) => (
            <td key={c} className={kind === "num" ? "num" : undefined}>
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
