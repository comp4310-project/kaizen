import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type IssueComment, type IssueCommentsOut, type Source, type Suggestion, type Unit } from "../api";
import { canReviewSuggestions, useAuth } from "../auth";
import { sourceName, words } from "../format";
import { EmptyState, ErrorNotice, SkeletonBlocks } from "../states";
import { SuggestionCard } from "../SuggestionCard";
import { CommentReview, IssueReview } from "../IssueReview";

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
  const issueId = Number(useParams().issueId);
  return <IssueDetail key={issueId} issueId={issueId} />;
}

function IssueDetail({ issueId }: { issueId: number }) {
  const { me } = useAuth();
  const navigate = useNavigate();
  const canReview = canReviewSuggestions(me);
  const [data, setData] = useState<IssueCommentsOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [moreError, setMoreError] = useState<unknown>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [unit, setUnit] = useState("");
  const [source, setSource] = useState<Source | "">("");
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [unitsError, setUnitsError] = useState<unknown>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);
  const [filtering, setFiltering] = useState(false);
  const scopedUnit = me?.role === "manager" ? me.unit ?? undefined : unit || undefined;
  const hasResults = data !== null && !filtering && error === null;

  useEffect(() => {
    if (!canReview) return;
    let current = true;
    api.units().then(
      (rows) => { if (current) setUnits(rows); },
      (cause: unknown) => { if (current) setUnitsError(cause); },
    );
    return () => { current = false; };
  }, [canReview]);

  useEffect(() => {
    let current = true;
    api.issueComments(issueId, { unit: scopedUnit, source: source || undefined, limit: PAGE_SIZE }).then(
      (out) => {
        if (current) {
          setData(out);
          setFiltering(false);
        }
      },
      (cause: unknown) => {
        if (current) {
          setError(cause);
          setFiltering(false);
        }
      },
    );
    return () => { current = false; };
  }, [issueId, scopedUnit, source]);

  function resetComments() {
    setError(null);
    setMoreError(null);
    setExportError(null);
    setFiltering(true);
  }

  async function loadMore() {
    if (!data) return;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const next = await api.issueComments(issueId, {
        unit: scopedUnit, source: source || undefined, limit: PAGE_SIZE, offset: data.comments.length,
      });
      setData((old) => old && { ...old, total: next.total, comments: [...old.comments, ...next.comments] });
    } catch (e) {
      setMoreError(e);
    } finally {
      setLoadingMore(false);
    }
  }

  async function exportComments() {
    if (!data?.comments.length) return;
    setExporting(true);
    setExportError(null);
    try {
      await api.downloadIssueComments(issueId, { unit: scopedUnit, source: source || undefined }, data.comments.length);
    } catch (cause) {
      setExportError(cause);
    } finally {
      setExporting(false);
    }
  }

  function updateComment(id: number, changes: Partial<Pick<IssueComment, "text" | "labels">>) {
    setData((old) => old && {
      ...old,
      comments: old.comments.map((row) => row.id === id ? { ...row, ...changes } : row),
    });
  }

  return (
    <section>
      <p className="breadcrumb">
        <Link to="/issues">All issues</Link>
      </p>
      <div className="page-head">
        <h1>{data ? `${data.issue.rank}. ${data.issue.name}` : error ? "Issue" : "Loading issue"}</h1>
        {canReview && data && (
          <IssueReview issue={data.issue}
            onRename={(issue) => setData((old) => old && { ...old, issue })}
            onMerge={(id) => navigate(`/issues/${id}`, { replace: true })} />
        )}
        {/* On narrow screens the suggestions sit below 50 comments, so give a way there. */}
        {canReview && !error && (
          <p className="narrow-only small">
            <a href="#suggestions-heading">Go to suggestions</a>
          </p>
        )}
      </div>
      <ErrorNotice error={error} />

      {(!error || data) && (
        <div className={canReview ? "detail-layout" : undefined}>
          <section aria-labelledby="comments-heading" className="detail-main">
            <div className="section-head">
              <h2 id="comments-heading">Comments{hasResults && data ? ` (${data.total})` : ""}</h2>
            </div>
            <div className="toolbar compare-filters">
              {canReview && (
                <div className="field">
                  <label htmlFor="comment-unit">Unit</label>
                  <select id="comment-unit" value={unit} disabled={!units || loadingMore || exporting}
                    onChange={(event) => { resetComments(); setUnit(event.target.value); }}>
                    <option value="">All units</option>
                    {units?.map(({ code, name }) => <option key={code} value={code}>{code} ({name})</option>)}
                  </select>
                </div>
              )}
              <div className="field">
                <label htmlFor="comment-source">Source</label>
                <select id="comment-source" value={source} disabled={loadingMore || exporting}
                  onChange={(event) => { resetComments(); setSource(event.target.value as Source | ""); }}>
                  <option value="">All sources</option>
                  <option value="patient_family">Patient or family</option>
                  <option value="staff">Staff</option>
                </select>
              </div>
              <button type="button" className="btn btn-secondary" disabled={!hasResults || !data?.comments.length || exporting || loadingMore}
                onClick={exportComments}>
                {exporting ? "Downloading" : "Download displayed comments as CSV"}
              </button>
            </div>
            <ErrorNotice error={unitsError} />
            <ErrorNotice error={exportError} />
            {hasResults && data && (
              <p className="muted small" role="status">
                Showing {data.comments.length} of {data.total}, most typical first. All text is de-identified.
                {me?.role === "manager" && ` Only comments from unit ${me.unit}.`}
              </p>
            )}
            {!error && (!data || filtering) && <SkeletonBlocks count={4} label="Loading comments" />}
            {hasResults && data && data.comments.length === 0 && (
              <EmptyState>
                <p>No comments match these filters.</p>
              </EmptyState>
            )}
            {hasResults && data && data.comments.length > 0 && (
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
                    {canReview && <CommentReview comment={c} onUpdate={updateComment} />}
                  </li>
                ))}
              </ol>
            )}
            <ErrorNotice error={moreError} />
            {hasResults && data && data.comments.length < data.total && (
              <button type="button" className="btn btn-secondary" onClick={loadMore} disabled={loadingMore || exporting}>
                {loadingMore ? "Loading" : `Show ${Math.min(PAGE_SIZE, data.total - data.comments.length)} more`}
              </button>
            )}
          </section>
          {canReview && <Suggestions issueId={issueId} />}
        </div>
      )}
    </section>
  );
}
