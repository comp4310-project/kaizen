import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type IssuesOut } from "../api";
import { useAuth } from "../auth";
import { errorText, percent, words } from "../format";

export function IssuesPage() {
  const { me } = useAuth();
  const [data, setData] = useState<IssuesOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.issues(50).then(setData, (e) => setError(errorText(e)));
  }, []);

  const isManager = me?.role === "manager";

  return (
    <section>
      <h1>Recurring issues</h1>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Loading issues...</p>}
      {data && !data.run && <p>No issues yet. Run <code>python -m kaizen.issues build</code> on the server first.</p>}
      {data?.run && (
        <>
          <p className="muted">
            From issue run {data.run.id} on {new Date(data.run.created_at).toLocaleString()}:{" "}
            {data.run.comments_used} comments grouped, {data.run.outliers} left out as outliers.
            {isManager && ` Showing only issues with comments from unit ${me?.unit}.`}
          </p>
          <div className="table-wrap">
            <table>
              <caption>Issues ranked by score, most pressing first</caption>
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col">Issue</th>
                  <th scope="col" className="num">
                    Comments
                  </th>
                  {isManager && (
                    <th scope="col" className="num">
                      From your unit
                    </th>
                  )}
                  <th scope="col" className="num">
                    Patient or family
                  </th>
                  <th scope="col" className="num">
                    Staff
                  </th>
                  <th scope="col">Main stage</th>
                  <th scope="col" className="num">
                    Negative
                  </th>
                  <th scope="col">Rising</th>
                </tr>
              </thead>
              <tbody>
                {data.issues.map((issue) => (
                  <tr key={issue.id}>
                    <td>{issue.rank}</td>
                    <th scope="row">
                      <Link to={`/issues/${issue.id}`}>{issue.name}</Link>
                    </th>
                    <td className="num">{issue.size}</td>
                    {isManager && <td className="num">{issue.unit_size ?? ""}</td>}
                    <td className="num">{issue.patient_count}</td>
                    <td className="num">{issue.staff_count}</td>
                    <td>{words(issue.main_stage)}</td>
                    <td className="num">{percent(issue.negative_share)}</td>
                    <td>{issue.rising ? <span className="tag rising">Rising</span> : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
