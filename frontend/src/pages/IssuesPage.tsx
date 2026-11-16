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

export function IssuesPage() {
  const { me } = useAuth();
  const [data, setData] = useState<IssuesOut | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.issues(50).then(setData, setError);
  }, []);

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

      <ErrorNotice error={error} />

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
