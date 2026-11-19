import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type OverviewOut, type ProcessRun } from "../api";
import { canReviewSuggestions, useAuth } from "../auth";
import { count, dateTime, percent, shortDate } from "../format";
import { ProcessPanel } from "../ProcessPanel";
import { EmptyState, ErrorNotice, SkeletonRows } from "../states";
import { WeeklyChart } from "../WeeklyChart";

function KeyNumbers({ data }: { data: OverviewOut }) {
  const c = data.comments;
  const items: [string, number, string?][] = [
    ["Comments", c.total],
    ["Patient or family", c.patient],
    ["Staff", c.staff],
    ["Labelled", c.labelled, `${c.confirmed.toLocaleString()} checked by a person`],
    ["Issues", data.issues.count],
    ["Rising", data.issues.rising],
  ];
  return (
    <dl className="key-numbers">
      {items.map(([label, value, note]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            <span className="key-value">{value.toLocaleString()}</span>
            {note && <span className="key-note muted small">{note}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** What to do next, in one line, from the counts. */
function NextStep({ data, canProcess, onStarted, onProcessed }: {
  data: OverviewOut;
  canProcess: boolean;
  onStarted: (run: ProcessRun) => void;
  onProcessed: () => void;
}) {
  const c = data.comments;
  const waiting = data.run ? c.new_since_run : c.unlabelled;
  const top = data.issues.top[0];

  let line;
  if (data.process?.status === "queued" || data.process?.status === "running") {
    line = <>New feedback is being processed. The numbers on this page update when it finishes.</>;
  } else if (c.total === 0) {
    line = canProcess
      ? <>No feedback yet. <Link to="/imports">Upload a CSV</Link> or share the <Link to="/feedback">feedback form</Link>.</>
      : <>No feedback from your unit yet.</>;
  } else if (waiting > 0 || c.unlabelled > 0) {
    const n = Math.max(waiting, c.unlabelled);
    const what = data.run
      ? `${count(n, "comment")} imported since the last run.`
      : `${count(n, "comment")} waiting to be labelled and grouped into issues.`;
    line = canProcess
      ? <>{what} {n === 1 ? "Process it" : "Process them"} to include {n === 1 ? "it" : "them"} in the issues.</>
      : <>{what} The QI team processes new feedback into the issues.</>;
  } else if (top) {
    line = <>Everything imported is in the issues. Start with the top issue, <Link to={`/issues/${top.id}`}>{top.name}</Link>.</>;
  } else {
    line = <>Everything imported is processed, and no issues were found. An issue needs at least 8 similar comments, or 2% of the comments if that is more.</>;
  }

  return (
    <section className="next-step" aria-labelledby="next-step-heading">
      <h2 id="next-step-heading">Next step</h2>
      <p>{line}</p>
      {canProcess && c.total > 0 && (
        <ProcessPanel waiting={waiting} initial={data.process} onStart={onStarted} onDone={onProcessed} />
      )}
    </section>
  );
}

export function OverviewPage() {
  const { me } = useAuth();
  const canProcess = canReviewSuggestions(me);
  const [data, setData] = useState<OverviewOut | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    api.overview().then(
      (out) => { setData(out); setError(null); },
      setError,
    );
  }, []);
  useEffect(load, [load]);

  return (
    <section>
      <div className="page-head">
        <h1>Overview</h1>
        {data && (
          <p className="muted">
            {data.unit ? `Unit ${data.unit} only. ` : "All units. "}
            {data.last_import ? `Last import ${dateTime(data.last_import)}. ` : "Nothing imported yet. "}
            {data.run ? `Issues last rebuilt ${dateTime(data.run.created_at)}.` : "Issues not built yet."}
          </p>
        )}
        {!data && !error && <p className="muted" role="status">Loading the overview.</p>}
      </div>
      <ErrorNotice error={error} />

      {data && (
        <>
          <KeyNumbers data={data} />
          <NextStep data={data} canProcess={canProcess} onProcessed={load}
            onStarted={(run) => setData((old) => old && { ...old, process: run })} />

          <div className="overview-grid">
            <section aria-labelledby="weekly-heading">
              <h2 id="weekly-heading">Comments per week</h2>
              {data.weeks.length ? (
                <>
                  <WeeklyChart id="overview-weeks" weeks={data.weeks} showTitle={false}
                    caption={`Comments per week, 12 weeks to ${shortDate(data.weeks_as_of ?? data.weeks[data.weeks.length - 1].end)}`} />
                  <p className="muted small">
                    Weeks end on the newest comment date, not today, the same way rising issues are worked out.
                  </p>
                </>
              ) : (
                <EmptyState><p>No comments yet, so there are no weeks to show.</p></EmptyState>
              )}
            </section>

            <section aria-labelledby="top-heading">
              <div className="section-head">
                <h2 id="top-heading">Top issues</h2>
                {data.issues.count > 3 && <Link to="/issues">All {data.issues.count} issues</Link>}
              </div>
              {data.issues.top.length ? (
                <div className="table-wrap" tabIndex={0} aria-labelledby="top-caption">
                  <table className="data-table">
                    <caption id="top-caption">The three highest ranked issues in the newest run</caption>
                    <thead>
                      <tr>
                        <th scope="col" className="num">Rank</th>
                        <th scope="col">Issue</th>
                        <th scope="col" className="num">{data.unit ? "Your unit" : "Comments"}</th>
                        <th scope="col" className="num col-optional">Negative</th>
                        <th scope="col">Rising</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.issues.top.map((issue) => (
                        <tr key={issue.id}>
                          <td className="num">{issue.rank}</td>
                          <th scope="row"><Link to={`/issues/${issue.id}`}>{issue.name}</Link></th>
                          <td className="num">{issue.unit_size ?? issue.size}</td>
                          <td className="num col-optional">{percent(issue.negative_share)}</td>
                          <td>{issue.rising ? <span className="badge badge-warn">Rising</span> : <span className="muted">No</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState>
                  <p>{data.run ? "The newest run found no issues." : "No issues yet."}</p>
                  {canProcess && !data.run && <p className="muted">Use Process new feedback above to build them.</p>}
                </EmptyState>
              )}
            </section>
          </div>
        </>
      )}

      {!data && !error && (
        <div className="table-wrap" aria-hidden="true">
          <table className="data-table"><tbody><SkeletonRows columns={["num", "wide", "num", "num", "text"]} rows={3} /></tbody></table>
        </div>
      )}
    </section>
  );
}
