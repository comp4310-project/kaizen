// Weekly counts for one issue, with one line on whether it is rising and what that means.
// The rule is kaizen.issues.rank: at least 3 comments in the last 7 days, and at least twice
// the weekly average of the 4 weeks before. Days count back from the newest comment date.
import { useEffect, useState } from "react";
import { api, type TrendOut } from "./api";
import { useAuth } from "./auth";
import { count, shortDate } from "./format";
import { ErrorNotice } from "./states";
import { WeeklyChart } from "./WeeklyChart";

function times(factor: number): string {
  return factor === 2 ? "twice" : `${factor} times`;
}

function risingLine(t: TrendOut): string {
  const average = t.prior_weekly_average.toLocaleString(undefined, { maximumFractionDigits: 2 });
  const facts = `${count(t.last_week, "comment")} in the 7 days to ${shortDate(t.as_of)}, against an average of ${average} a week in the 4 weeks before.`;
  const rule = `An issue is rising when its last 7 days have at least ${t.rising_min_comments} comments and at least ${times(t.rising_factor)} that average.`;
  return `${facts} ${rule}`;
}

export function IssueTrend({ issueId }: { issueId: number }) {
  const { me } = useAuth();
  const [data, setData] = useState<TrendOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    setError(null);
    api.issueTrend(issueId).then(
      (out) => { if (current) setData(out); },
      (cause: unknown) => { if (current) setError(cause); },
    );
    return () => { current = false; };
  }, [issueId, attempt]);

  if (error !== null) return <ErrorNotice error={error} onRetry={() => setAttempt((n) => n + 1)} />;
  if (!data) {
    // Same height as the chart, so the comments below do not jump when it arrives.
    return (
      <div className="issue-trend issue-trend-loading" aria-hidden="true">
        <span className="skeleton skeleton-wide" />
        <span className="skeleton skeleton-chart" />
      </div>
    );
  }
  return (
    <section className="issue-trend" aria-labelledby="trend-heading">
      <h2 id="trend-heading" className="visually-hidden">Trend</h2>
      <p>
        {data.rising ? <span className="badge badge-warn">Rising</span> : <strong>Not rising.</strong>} {risingLine(data)}
      </p>
      <WeeklyChart id={`issue-${issueId}-weeks`} weeks={data.weeks}
        caption={data.unit ? `Comments per week from unit ${data.unit}` : "Comments per week"} />
      {me?.role === "manager" && (
        <p className="muted small">The chart shows unit {data.unit} only. Rising is worked out on the whole issue, across all units.</p>
      )}
    </section>
  );
}
