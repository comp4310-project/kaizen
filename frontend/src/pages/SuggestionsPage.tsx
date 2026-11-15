import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Suggestion, type SuggestionStatus } from "../api";
import { EmptyState, ErrorNotice, SkeletonBlocks } from "../states";
import { SuggestionCard } from "../SuggestionCard";

const FILTERS: { value: SuggestionStatus | ""; label: string }[] = [
  { value: "suggested", label: "Waiting for a decision" },
  { value: "accepted", label: "Accepted" },
  { value: "edited", label: "Edited" },
  { value: "rejected", label: "Rejected" },
  { value: "", label: "All" },
];

export function SuggestionsPage() {
  const [status, setStatus] = useState<SuggestionStatus | "">("suggested");
  const [rows, setRows] = useState<Suggestion[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setRows(null);
    setError(null);
    api.suggestions({ status: status || undefined, limit: 100 }).then((out) => setRows(out.suggestions), setError);
  }, [status]);

  // Keep a decided card on screen with its new status, so the person sees what happened.
  // It drops out of the "waiting" list the next time the list loads.
  function decided(updated: Suggestion) {
    setRows((old) => (old ?? []).map((s) => (s.id === updated.id ? updated : s)));
  }

  return (
    <section>
      <div className="page-head">
        <h1>Suggestion review</h1>
        <p className="muted">
          Nothing the model drafts is final. A suggestion waits here until someone accepts, edits or rejects it, and
          every decision is logged.
        </p>
      </div>
      <div className="toolbar">
        <div className="field field-inline">
          <label htmlFor="status-filter">Show</label>
          <select id="status-filter" value={status} onChange={(e) => setStatus(e.target.value as SuggestionStatus | "")}>
            {FILTERS.map((f) => (
              <option key={f.label} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
        {rows && rows.length > 0 && (
          <p className="muted small" role="status">
            {rows.length} shown
          </p>
        )}
      </div>
      <ErrorNotice error={error} />
      {!rows && !error && <SkeletonBlocks count={2} label="Loading suggestions" card />}
      {rows && rows.length === 0 && (
        <EmptyState>
          <p>{status === "suggested" ? "Nothing is waiting for a decision." : "No suggestions with this status."}</p>
          <p className="muted">
            Suggestions are drafted from an issue's page. Open one from <Link to="/issues">Issues</Link> and use Draft
            suggestions.
          </p>
        </EmptyState>
      )}
      <div className="card-grid">
        {rows?.map((s) => (
          <SuggestionCard key={s.id} suggestion={s} onDecided={decided} />
        ))}
      </div>
    </section>
  );
}
