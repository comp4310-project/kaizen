import { useEffect, useState } from "react";
import { api, type CompareBy, type CompareOut, type Unit } from "../api";
import { useAuth } from "../auth";
import { percent, sortUnits, words } from "../format";
import { useDebounced } from "../hooks";
import { EmptyState, ErrorNotice, SkeletonRows } from "../states";

const groupNames: Record<CompareBy, string> = {
  category: "Category",
  stage: "Stage of care",
  unit: "Unit",
};

// The API has no category filter yet, so rows cannot link to the comments they count and
// switching Group by starts again from every comment. See TASKS.md, FR5 follow-up.
const groupMeaning: Record<CompareBy, string> = {
  category: "Each row counts the labelled comments with that category from each group, across all issues and the filters above.",
  stage: "Each row counts the labelled comments about that stage of care from each group, across all issues and the filters above.",
  unit: "Each row counts the labelled comments recorded against that unit from each group, across all issues and the filters above.",
};

function CountCell({ count, max }: { count: number; max: number }) {
  return (
    <td className="num">
      <span className="share">
        <span className="share-track" aria-hidden="true">
          <span className="bar" style={{ width: percent(count / max) }} />
        </span>
        {count}
      </span>
    </td>
  );
}

export function ComparePage() {
  const { me } = useAuth();
  const isManager = me?.role === "manager";
  const [by, setBy] = useState<CompareBy>("category");
  const [unit, setUnit] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [unitError, setUnitError] = useState<unknown>(null);
  const scopedUnit = isManager ? me?.unit ?? undefined : unit || undefined;
  const invalidRange = Boolean(from && to && from > to);
  // Reload once the filters have settled, not for every option passed with the arrow keys.
  const applied = useDebounced(JSON.stringify([by, scopedUnit ?? null, from, to]));
  const [appliedBy, appliedUnit, appliedFrom, appliedTo] = JSON.parse(applied) as [CompareBy, string | null, string, string];

  useEffect(() => {
    if (isManager) return;
    let current = true;
    api.units().then(
      (result) => {
        if (current) setUnits(sortUnits(result));
      },
      (error: unknown) => {
        if (current) setUnitError(error);
      },
    );
    return () => {
      current = false;
    };
  }, [isManager]);

  return (
    <section>
      <div className="page-head">
        <h1>Compare patient or family and staff feedback</h1>
        {isManager && <p className="muted">Showing feedback from your unit, {me?.unit}.</p>}
      </div>

      <div className="toolbar compare-filters">
        <div className="field">
          <label htmlFor="compare-by">Group by</label>
          <select id="compare-by" value={by} onChange={(event) => setBy(event.target.value as CompareBy)}>
            <option value="category">Category</option>
            <option value="stage">Stage of care</option>
            <option value="unit">Unit</option>
          </select>
        </div>
        {!isManager && (
          <div className="field">
            <label htmlFor="compare-unit">Unit</label>
            <select id="compare-unit" value={unit} onChange={(event) => setUnit(event.target.value)} disabled={!units}>
              <option value="">All units</option>
              {units?.map(({ code, name }) => <option key={code} value={code}>{code} ({name})</option>)}
            </select>
          </div>
        )}
        <div className="field">
          <label htmlFor="compare-from">From date</label>
          <input id="compare-from" type="date" value={from} onChange={(event) => setFrom(event.target.value)}
            aria-invalid={invalidRange} aria-describedby={invalidRange ? "compare-date-error" : undefined} />
        </div>
        <div className="field">
          <label htmlFor="compare-to">To date</label>
          <input id="compare-to" type="date" value={to} onChange={(event) => setTo(event.target.value)}
            aria-invalid={invalidRange} aria-describedby={invalidRange ? "compare-date-error" : undefined} />
        </div>
      </div>
      {unitError !== null && (
        <div>
          <p>Unit choices could not load. Reload the page to try again.</p>
          <ErrorNotice error={unitError} />
        </div>
      )}
      {invalidRange || (appliedFrom && appliedTo && appliedFrom > appliedTo) ? (
        <div id="compare-date-error">
          <ErrorNotice error={new Error("Choose an end date on or after the start date.")} />
        </div>
      ) : (
        <CompareResults key={applied} by={appliedBy} unit={appliedUnit ?? undefined} from={appliedFrom} to={appliedTo} />
      )}
    </section>
  );
}

function CompareResults({ by, unit, from, to }: { by: CompareBy; unit?: string; from: string; to: string }) {
  const [data, setData] = useState<CompareOut | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let current = true;
    api.compare({ by, unit, date_from: from || undefined, date_to: to || undefined }).then(
      (result) => {
        if (current) setData(result);
      },
      (cause: unknown) => {
        if (current) setError(cause);
      },
    );
    return () => {
      current = false;
    };
  }, [by, unit, from, to]);

  if (error !== null) return <ErrorNotice error={error} />;

  const max = Math.max(1, ...(data?.rows.map((row) => Math.max(row.patient, row.staff)) ?? []));
  return (
    <>
      <p role="status" className="muted">
        {data
          ? `Labelled comments: ${data.totals.patient} patient or family, ${data.totals.staff} staff.`
          : "Loading comparison."}
      </p>
      {data?.rows.length === 0 ? (
        <EmptyState>
          {data.totals.patient + data.totals.staff === 0 ? (
            <>
              <p>No labelled comments in this range.</p>
              <p className="muted">Change the filters or check whether feedback has been labelled.</p>
            </>
          ) : (
            <p>No category labels in this range. Group by stage or unit to see these comments.</p>
          )}
        </EmptyState>
      ) : (
        <>
          <div className="table-wrap" tabIndex={0} aria-labelledby="compare-caption">
            <table className="data-table">
              <caption id="compare-caption">Feedback by {groupNames[by].toLowerCase()}</caption>
              <thead>
                <tr>
                  <th scope="col">{groupNames[by]}</th>
                  <th scope="col" className="num">Patient or family</th>
                  <th scope="col" className="num">Staff</th>
                  <th scope="col">Reported by</th>
                </tr>
              </thead>
              <tbody aria-busy={!data}>
                {!data && <SkeletonRows columns={["wide", "num", "num", "text"]} />}
                {data?.rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{words(row.key)}</th>
                    <CountCell count={row.patient} max={max} />
                    <CountCell count={row.staff} max={max} />
                    <td>{row.only
                      ? <span className="badge badge-warn">{row.only === "patient" ? "Only patients or families" : "Only staff"}</span>
                      : "Both groups"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data && <p className="muted small">{groupMeaning[data.by]}</p>}
          {data?.by === "category" && (
            <p className="muted small">Comments can count in more than one category. Comments without a category only appear in the totals.</p>
          )}
        </>
      )}
    </>
  );
}
