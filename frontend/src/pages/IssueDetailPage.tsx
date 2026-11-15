import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type IssueComment, type IssueCommentsOut, type Suggestion } from "../api";
import { canReviewSuggestions, useAuth } from "../auth";
import { errorText, sourceName, words } from "../format";
import { SuggestionCard } from "../SuggestionCard";

const PAGE_SIZE = 50;

function Labels({ comment }: { comment: IssueComment }) {
  const l = comment.labels;
  if (!l) return <span className="muted">Not labelled yet</span>;
  return (
    <ul className="labels" aria-label="Labels">
      <li>Sentiment: {l.sentiment}</li>
      <li>Stage: {words(l.stage)}</li>
      <li>Urgency: {l.urgency}</li>
      <li>Categories: {l.categories.length ? l.categories.map(words).join(", ") : "none"}</li>
      <li>{l.status === "confirmed" ? "Checked by a person" : "Suggested by the model"}</li>
    </ul>
  );
}

function Suggestions({ issueId }: { issueId: number }) {
  const [rows, setRows] = useState<Suggestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    api.issueSuggestions(issueId).then(
      (out) => setRows(out.suggestions),
      (e) => setError(errorText(e)),
    );
  }, [issueId]);

  async function draft() {
    setDrafting(true);
    setError(null);
    setNote(null);
    try {
      const out = await api.draftSuggestions(issueId);
      setRows((old) => [...out.suggestions, ...(old ?? [])]);
      const dropped = out.dropped
        ? ` ${out.dropped} dropped by the citation check: ${out.reasons.join("; ")}.`
        : "";
      setNote(`Drafted ${out.suggestions.length} suggestions.${dropped}`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setDrafting(false);
    }
  }

  function replace(updated: Suggestion) {
    setRows((old) => (old ?? []).map((s) => (s.id === updated.id ? updated : s)));
  }

  return (
    <section aria-labelledby="suggestions-heading">
      <h2 id="suggestions-heading">Suggestions</h2>
      <p className="muted">
        Drafting sends the issue name, keywords and stage to the model with the closest document passages. It never
        sends comment text. It can take up to a minute.
      </p>
      <button type="button" onClick={draft} disabled={drafting} aria-describedby="draft-status">
        {drafting ? "Drafting..." : "Draft suggestions"}
      </button>
      <p id="draft-status" role="status">
        {note}
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {rows && rows.length === 0 && <p>No suggestions for this issue yet.</p>}
      {rows?.map((s) => (
        <SuggestionCard key={s.id} suggestion={s} onDecided={replace} showIssue={false} />
      ))}
    </section>
  );
}

export function IssueDetailPage() {
  const { me } = useAuth();
  const issueId = Number(useParams().issueId);
  const [data, setData] = useState<IssueCommentsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    setData(null);
    setError(null);
    api.issueComments(issueId, { limit: PAGE_SIZE }).then(setData, (e) => setError(errorText(e)));
  }, [issueId]);

  async function loadMore() {
    if (!data) return;
    setLoadingMore(true);
    try {
      const next = await api.issueComments(issueId, { limit: PAGE_SIZE, offset: data.comments.length });
      setData({ ...next, comments: [...data.comments, ...next.comments] });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <section>
      <p>
        <Link to="/issues">Back to all issues</Link>
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Loading comments...</p>}
      {data && (
        <>
          <h1>
            Issue {data.issue.rank}: {data.issue.name}
          </h1>
          {canReviewSuggestions(me) && <Suggestions issueId={issueId} />}

          <section aria-labelledby="comments-heading">
            <h2 id="comments-heading">Comments ({data.total})</h2>
            <p className="muted">
              Showing {data.comments.length} of {data.total}, most typical first. All text is de-identified.
              {me?.role === "manager" && ` Only comments from unit ${me.unit} are shown.`}
            </p>
            <ol className="comments">
              {data.comments.map((c) => (
                <li key={c.id} className="card">
                  <p className="comment-meta">
                    Comment {c.id}, {sourceName(c.source)}, unit {c.unit}, {c.date}
                    {c.typical && <span className="tag">Typical</span>}
                  </p>
                  <p className="comment-text">{c.text}</p>
                  <Labels comment={c} />
                </li>
              ))}
            </ol>
            {data.comments.length < data.total && (
              <button type="button" className="secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading..." : "Show more comments"}
              </button>
            )}
          </section>
        </>
      )}
    </section>
  );
}
