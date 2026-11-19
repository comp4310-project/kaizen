import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type CommentListFilters, type CommentRow, type CommentsOut, type Source } from "../api";
import { useAuth } from "../auth";
import { count, sourceName, words } from "../format";
import { EmptyState, ErrorNotice, SkeletonBlocks } from "../states";

const PAGE_SIZE = 50;
const KEYS = ["unit", "source", "category", "stage", "labelled", "date_from", "date_to"] as const;

function filtersFrom(params: URLSearchParams): CommentListFilters {
  const filters: Record<string, string> = {};
  for (const key of KEYS) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  return filters as CommentListFilters;
}

/** The filters as one plain sentence, e.g. "Labelled comments with category communication, from staff, unit 4B." */
function describe(f: CommentListFilters, managerUnit: string | null): string {
  const parts: string[] = [];
  if (f.category) parts.push(`with category ${words(f.category)}`);
  if (f.stage) parts.push(`about ${words(f.stage)}`);
  if (f.source) parts.push(f.source === "staff" ? "from staff" : "from patients or families");
  const unit = managerUnit ?? f.unit;
  parts.push(unit ? `unit ${unit}` : "all units");
  if (f.date_from && f.date_to) parts.push(`dated ${f.date_from} to ${f.date_to}`);
  else if (f.date_from) parts.push(`dated ${f.date_from} or later`);
  else if (f.date_to) parts.push(`dated ${f.date_to} or earlier`);
  const what = f.labelled === "false" ? "Comments not labelled yet" : f.labelled === "true" || f.category || f.stage ? "Labelled comments" : "All comments";
  return `${what} ${parts.join(", ")}.`;
}

function Labels({ comment }: { comment: CommentRow }) {
  const l = comment.labels;
  if (!l) return <p className="muted small">Not labelled yet.</p>;
  return (
    <dl className="labels">
      <div><dt>Sentiment</dt><dd>{l.sentiment}</dd></div>
      <div><dt>Stage</dt><dd>{words(l.stage)}</dd></div>
      <div><dt>Urgency</dt><dd>{l.urgency}</dd></div>
      <div><dt>Categories</dt><dd>{l.categories.length ? l.categories.map(words).join(", ") : "none"}</dd></div>
      <div><dt>Labels</dt><dd>{l.status === "confirmed" ? "checked by a person" : "suggested automatically, not yet checked"}</dd></div>
    </dl>
  );
}

export function CommentsPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const filters = filtersFrom(params);
  const key = JSON.stringify(filters);
  const managerUnit = me?.role === "manager" ? me.unit : null;
  const [data, setData] = useState<CommentsOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<unknown>(null);

  useEffect(() => {
    let current = true;
    setData(null);
    setError(null);
    setMoreError(null);
    api.comments({ ...JSON.parse(key), limit: PAGE_SIZE }).then(
      (out) => { if (current) setData(out); },
      (cause: unknown) => { if (current) setError(cause); },
    );
    return () => { current = false; };
  }, [key]);

  async function loadMore() {
    if (!data) return;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const next = await api.comments({ ...filters, limit: PAGE_SIZE, offset: data.comments.length });
      setData((old) => old && { total: next.total, comments: [...old.comments, ...next.comments] });
    } catch (cause) {
      setMoreError(cause);
    } finally {
      setLoadingMore(false);
    }
  }

  function setSource(source: Source | "") {
    const next = new URLSearchParams(params);
    if (source) next.set("source", source);
    else next.delete("source");
    setParams(next, { replace: true });
  }

  return (
    <section>
      <p className="breadcrumb"><Link to="/compare">Compare</Link></p>
      <div className="page-head">
        <h1>Comments</h1>
        <p className="muted">{describe(filters, managerUnit)} All text is de-identified.</p>
      </div>

      <div className="toolbar compare-filters">
        <div className="field">
          <label htmlFor="comments-source">Source</label>
          <select id="comments-source" value={filters.source ?? ""} disabled={loadingMore}
            onChange={(event) => setSource(event.target.value as Source | "")}>
            <option value="">Both groups</option>
            <option value="patient_family">Patient or family</option>
            <option value="staff">Staff</option>
          </select>
        </div>
      </div>

      <ErrorNotice error={error} />
      {!error && (
        <p className="muted small" role="status">
          {data ? `Showing ${data.comments.length} of ${count(data.total, "comment")}, in the order they were imported.` : "Loading comments."}
        </p>
      )}
      {!error && !data && <SkeletonBlocks count={4} label="Loading comments" />}
      {data && data.comments.length === 0 && (
        <EmptyState>
          <p>No comments match these filters.</p>
          <p className="muted">Go back to <Link to="/compare">Compare</Link> and pick another row.</p>
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
  );
}
