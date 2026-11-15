import { useEffect, useState } from "react";
import { api, type Suggestion, type SuggestionStatus } from "../api";
import { errorText } from "../format";
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    setError(null);
    api.suggestions({ status: status || undefined, limit: 100 }).then(
      (out) => setRows(out.suggestions),
      (e) => setError(errorText(e)),
    );
  }, [status]);

  // A decided suggestion leaves the "waiting" list but stays visible under the other filters.
  function decided(updated: Suggestion) {
    setRows((old) =>
      (old ?? [])
        .map((s) => (s.id === updated.id ? updated : s))
        .filter((s) => !status || s.status === status),
    );
  }

  return (
    <section>
      <h1>Suggestion review</h1>
      <p className="muted">
        Nothing the model drafts is final. Each suggestion stays waiting until someone accepts, edits or rejects it, and
        every decision is logged.
      </p>
      <label htmlFor="status-filter">Show</label>
      <select id="status-filter" value={status} onChange={(e) => setStatus(e.target.value as SuggestionStatus | "")}>
        {FILTERS.map((f) => (
          <option key={f.label} value={f.value}>
            {f.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!rows && !error && <p role="status">Loading suggestions...</p>}
      {rows && rows.length === 0 && <p>No suggestions here.</p>}
      {rows?.map((s) => (
        <SuggestionCard key={s.id} suggestion={s} onDecided={decided} />
      ))}
    </section>
  );
}
