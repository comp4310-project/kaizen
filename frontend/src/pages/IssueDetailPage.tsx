import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type IssueComment, type IssueCommentsOut, type Suggestion } from "../api";
import { canReviewSuggestions, useAuth } from "../auth";
import { sourceName, words } from "../format";
import { EmptyState, ErrorNotice, SkeletonBlocks } from "../states";
import { SuggestionCard } from "../SuggestionCard";

const PAGE_SIZE = 50;

function Labels({ comment }: { comment: IssueComment }) {
  const l = comment.labels;
  if (!l) return <p className="muted small">Not labelled yet.</p>;
  return (
    <dl className="labels">
      <div>
        <dt>Sentiment</dt>
        <dd>{l.sentiment}</dd>
      </div>
      <div>
        <dt>Stage</dt>
        <dd>{words(l.stage)}</dd>
      </div>
      <div>
        <dt>Urgency</dt>
        <dd>{l.urgency}</dd>
      </div>
      <div>
        <dt>Categories</dt>
        <dd>{l.categories.length ? l.categories.map(words).join(", ") : "none"}</dd>
      </div>
      <div>
        <dt>Labels</dt>
        <dd>{l.status === "confirmed" ? "checked by a person" : "suggested by the model"}</dd>
      </div>
    </dl>
  );
}

function Suggestions({ issueId }: { issueId: number }) {
  const [rows, setRows] = useState<Suggestion[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<unknown>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    api.issueSuggestions(issueId).then((out) => setRows(out.suggestions), setError);
  }, [issueId]);

  async function draft() {
    setDrafting(true);
    setDraftError(null);
    setNote("");
    try {
      const out = await api.draftSuggestions(issueId);
      setRows((old) => [...out.suggestions, ...(old ?? [])]);
      const dropped = out.dropped ? ` ${out.dropped} dropped by the citation check: ${out.reasons.join("; ")}.` : "";
      setNote(`Drafted ${out.suggestions.length}.${dropped}`);
    } catch (e) {
      setDraftError(e);
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
        <button type="button" className="btn btn-primary" onClick={draft} disabled={drafting}>
          {drafting ? "Drafting" : "Draft suggestions"}
        </button>
      </div>
      <p className="muted small">
        Sends the issue name, keywords and stage to the model with the closest document passages, never comment text.
        Takes up to a minute.
      </p>
      <p role="status" className="small">
        {drafting ? "Drafting, this can take up to a minute." : note}
      </p>
      <ErrorNotice error={draftError} />
      <ErrorNotice error={error} />
      {!rows && !error && <SkeletonBlocks count={1} label="Loading suggestions" card />}
      {rows && rows.length === 0 && (
        <EmptyState>
          <p>No suggestions for this issue yet. Use Draft suggestions to ask for two or three.</p>
        </EmptyState>
      )}
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
  const [error, setError] = useState<unknown>(null);
  const [moreError, setMoreError] = useState<unknown>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    setData(null);
    setError(null);
    api.issueComments(issueId, { limit: PAGE_SIZE }).then(setData, setError);
  }, [issueId]);

  async function loadMore() {
    if (!data) return;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const next = await api.issueComments(issueId, { limit: PAGE_SIZE, offset: data.comments.length });
      setData({ ...next, comments: [...data.comments, ...next.comments] });
    } catch (e) {
      setMoreError(e);
    } finally {
      setLoadingMore(false);
    }
  }

  const showSuggestions = canReviewSuggestions(me);

  return (
    <section>
      <p className="breadcrumb">
        <Link to="/issues">All issues</Link>
      </p>
      <div className="page-head">
        <h1>{data ? `${data.issue.rank}. ${data.issue.name}` : error ? "Issue" : "Loading issue"}</h1>
        {/* On narrow screens the suggestions sit below 50 comments, so give a way there. */}
        {showSuggestions && !error && (
          <p className="narrow-only small">
            <a href="#suggestions-heading">Go to suggestions</a>
          </p>
        )}
      </div>
      <ErrorNotice error={error} />

      {!error && (
        <div className={showSuggestions ? "detail-layout" : undefined}>
          <section aria-labelledby="comments-heading" className="detail-main">
            <div className="section-head">
              <h2 id="comments-heading">Comments{data ? ` (${data.total})` : ""}</h2>
            </div>
            {data && (
              <p className="muted small">
                Showing {data.comments.length} of {data.total}, most typical first. All text is de-identified.
                {me?.role === "manager" && ` Only comments from unit ${me.unit}.`}
              </p>
            )}
            {!data && <SkeletonBlocks count={4} label="Loading comments" />}
            {data && data.comments.length === 0 && (
              <EmptyState>
                <p>No comments in this issue.</p>
              </EmptyState>
            )}
            {data && data.comments.length > 0 && (
              <ol className="comment-list">
                {data.comments.map((c) => (
                  <li key={c.id}>
                    <p className="comment-meta">
                      <span>Comment {c.id}</span>
                      <span>{sourceName(c.source)}</span>
                      <span>Unit {c.unit}</span>
                      <span className="num">{c.date}</span>
                      {c.typical && <span className="badge">Typical</span>}
                    </p>
                    <p className="comment-text">{c.text}</p>
                    <Labels comment={c} />
                  </li>
                ))}
              </ol>
            )}
            <ErrorNotice error={moreError} />
            {data && data.comments.length < data.total && (
              <button type="button" className="btn btn-secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading" : `Show ${Math.min(PAGE_SIZE, data.total - data.comments.length)} more`}
              </button>
            )}
          </section>
          {showSuggestions && <Suggestions issueId={issueId} />}
        </div>
      )}
    </section>
  );
}
