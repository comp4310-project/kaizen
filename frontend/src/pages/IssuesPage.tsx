import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type IssuesOut } from "../api";
import { useAuth } from "../auth";
import { dateTime, percent, words } from "../format";
import { EmptyState, ErrorNotice, SkeletonRows } from "../states";

/** A small bar for a share from 0 to 1. Decorative: the number next to it is what is read out. */
function ShareBar({ share }: { share: number }) {
  return <span className="bar" style={{ width: `${Math.round(share * 100)}%` }} aria-hidden="true" />;
}

/**
 * Plain explanations of the table's terms, for readers who do not work in QI. Visible on
 * a click rather than on hover, so it works by keyboard and touch. The wording matches
 * kaizen/issues/rank.py.
 */
function ColumnHelp() {
  return (
    <details className="help">
      <summary>What these columns mean</summary>
      <dl className="help-list">
        <dt>Rank</dt>
        <dd>
          The order of the list, most pressing first. Issues with more comments come higher, and more so when
          those comments are negative or marked high urgency.
        </dd>
        <dt>Comments, Patient or family, Staff</dt>
        <dd>How many comments make up the issue, and how many came from patients or families and from staff.</dd>
        <dt>Main stage</dt>
        <dd>
          The part of the hospital stay most of its comments are about, for example admission, care on the ward or
          discharge.
        </dd>
        <dt>Negative</dt>
        <dd>The share of its comments that are complaints rather than praise or neutral remarks.</dd>
        <dt>Rising</dt>
        <dd>
          At least 3 comments in the most recent week of feedback, and at least twice as many as in an average
          week over the month before. It is an early warning, not a measure of how serious the issue is.
        </dd>
        <dt>Outliers</dt>
        <dd>Comments that were not similar enough to any issue to be grouped. They are kept but not listed here.</dd>
        <dt>Typical example</dt>
        <dd>On an issue&apos;s page, the comments that best show what the issue is about. They are listed first.</dd>
        <dt>Suggested automatically</dt>
        <dd>
          Labels such as sentiment and stage of care that the model set and nobody has checked yet. QI staff
          confirm or correct them on the issue&apos;s page.
        </dd>
      </dl>
    </details>
  );
}

export function IssuesPage() {
  const { me } = useAuth();
  const [data, setData] = useState<IssuesOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    api.issues(50).then(
      (out) => { if (current) setData(out); },
      (cause: unknown) => { if (current) setError(cause); },
    );
    return () => { current = false; };
  }, [attempt]);

  function retry() {
    setError(null);
    setData(null);
    setAttempt((n) => n + 1);
  }

  const isManager = me?.role === "manager";
  const columns: ("text" | "num" | "wide")[] = isManager
    ? ["num", "wide", "num", "num", "num", "num", "text", "num", "text"]
    : ["num", "wide", "num", "num", "num", "text", "num", "text"];

  return (
    <section>
      <div className="page-head">
        <h1>Recurring issues</h1>
        {!data && !error && (
          <p className="muted" role="status">
            Loading issues. The list replaces the grey rows when it arrives.
          </p>
        )}
        {data?.run && (
          <p className="muted">
            Run {data.run.id}, {dateTime(data.run.created_at)}. {data.run.comments_used} comments grouped into issues,{" "}
            {data.run.outliers} left out because they did not match any issue (outliers).
            {isManager && ` Only issues with comments from unit ${me?.unit}.`}
          </p>
        )}
      </div>

      <ErrorNotice error={error} onRetry={retry} />

      {data && !data.run && (
        <EmptyState>
          <p>No issues yet.</p>
          <p className="muted">
            Run <code>python -m kaizen.issues build</code> on the server, then reload this page.
          </p>
        </EmptyState>
      )}
      {data?.run && data.issues.length === 0 && (
        <EmptyState>
          <p>No issues in the newest run{isManager ? ` have comments from unit ${me?.unit}` : ""}.</p>
        </EmptyState>
      )}

      {!error && (!data || data.issues.length > 0) && <ColumnHelp />}

      {!error && (!data || data.issues.length > 0) && (
        <div className="table-wrap" tabIndex={0} aria-labelledby="issues-caption">
          <table className="data-table">
            <caption id="issues-caption">Issues ranked by score, most pressing first</caption>
            <thead>
              <tr>
                <th scope="col" className="num">
                  Rank
                </th>
                <th scope="col">Issue</th>
                <th scope="col" className="num">
                  Comments
                </th>
                {isManager && (
                  <th scope="col" className="num">
                    Your unit
                  </th>
                )}
                <th scope="col" className="num">
                  Patient or family
                </th>
                <th scope="col" className="num">
                  Staff
                </th>
                <th scope="col" className="col-optional">Main stage</th>
                <th scope="col" className="num">
                  Negative
                </th>
                <th scope="col">Rising</th>
              </tr>
            </thead>
            <tbody aria-busy={!data}>
              {!data && <SkeletonRows columns={columns} rows={7} optional={[columns.length - 3]} />}
              {data?.issues.map((issue) => (
                <tr key={issue.id}>
                  <td className="num">{issue.rank}</td>
                  <th scope="row" className="issue-name">
                    <Link to={`/issues/${issue.id}`}>{issue.name}</Link>
                    {/* Below 900px the stage column is hidden and the stage sits here instead. */}
                    <span className="narrow-stage muted small">Main stage: {words(issue.main_stage)}</span>
                  </th>
                  <td className="num">{issue.size}</td>
                  {isManager && <td className="num">{issue.unit_size ?? ""}</td>}
                  <td className="num">{issue.patient_count}</td>
                  <td className="num">{issue.staff_count}</td>
                  <td className="nowrap col-optional">{words(issue.main_stage)}</td>
                  <td className="num">
                    <span className="share">
                      <span className="share-track">
                        <ShareBar share={issue.negative_share} />
                      </span>
                      {percent(issue.negative_share)}
                    </span>
                  </td>
                  <td>{issue.rising ? <span className="badge badge-warn">Rising</span> : <span className="muted">No</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
