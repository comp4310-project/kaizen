import { useEffect, useState } from "react";
import { api, type Suggestion } from "./api";
import { EmptyState, ErrorNotice, SkeletonBlocks } from "./states";
import { SuggestionCard } from "./SuggestionCard";

/**
 * The suggestions panel on an issue's page, for QI and admin: what has been drafted for the
 * issue, and the Draft suggestions button. Drafting is one model request while the person
 * waits, so the button says how long it can take, and a failure (for example the model not
 * running, a 503) is shown under it with Try again.
 */
export function IssueSuggestions({ issueId }: { issueId: number }) {
  const [rows, setRows] = useState<Suggestion[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<unknown>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    let current = true;
    setError(null);
    api.issueSuggestions(issueId).then(
      (out) => { if (current) setRows(out.suggestions); },
      (cause: unknown) => { if (current) setError(cause); },
    );
    return () => { current = false; };
  }, [issueId, attempt]);

  async function draft() {
    if (drafting) return;
    setDrafting(true);
    setDraftError(null);
    setNote("");
    try {
      const out = await api.draftSuggestions(issueId);
      setRows((old) => [...out.suggestions, ...(old ?? [])]);
      const n = out.suggestions.length;
      const kept = n === 0 ? "No suggestion passed the citation check." : `Drafted ${n === 1 ? "1 suggestion" : `${n} suggestions`}.`;
      const dropped = out.dropped
        ? ` ${out.dropped} ${out.dropped === 1 ? "was" : "were"} left out because a quote was missing or could not be found in its document.`
        : "";
      setNote(`${kept}${dropped}`);
    } catch (cause) {
      setDraftError(cause);
    } finally {
      setDrafting(false);
    }
  }

  function replace(updated: Suggestion) {
    setRows((old) => (old ?? []).map((s) => (s.id === updated.id ? updated : s)));
  }

  return (
    <section aria-labelledby="suggestions-heading" className="detail-aside">
      <div className="section-head">
        <h2 id="suggestions-heading">Suggestions</h2>
      </div>
      <p className="small">
        Drafts up to three changes for this issue, each backed by quotes from the standards and policies. The model
        gets the issue name, keywords and stage of care, never the comments themselves.
      </p>
      <div className="draft-action">
        <button type="button" className="btn btn-primary" onClick={draft} disabled={drafting}>
          {drafting ? "Drafting, this can take up to a minute" : "Draft suggestions"}
        </button>
      </div>
      <p role="status" className="small">{drafting ? "Drafting suggestions." : note}</p>
      <ErrorNotice error={draftError} onRetry={draft} />
      <ErrorNotice error={error} onRetry={() => setAttempt((n) => n + 1)} />
      {!rows && !error && <SkeletonBlocks count={1} label="Loading suggestions" card />}
      {rows && rows.length === 0 && (
        <EmptyState>
          <p>No suggestions for this issue yet. Use Draft suggestions to ask for up to three.</p>
        </EmptyState>
      )}
      {rows?.map((s) => (
        <SuggestionCard key={s.id} suggestion={s} onDecided={replace} showIssue={false} />
      ))}
    </section>
  );
}
