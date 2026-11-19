// "Process new feedback": labels every comment that has no labels yet and rebuilds the
// issues, in the background on the server (POST /runs). While a run is queued or running
// the status is fetched every 2 seconds. QI and admin only; the caller checks the role.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type ProcessRun } from "./api";
import { count, dateTime } from "./format";
import { ErrorNotice } from "./states";

const POLL_MS = 2000;

function active(run: ProcessRun | null): boolean {
  return run?.status === "queued" || run?.status === "running";
}

function labellerName(name: string | null): string {
  if (!name) return "";
  return name === "tfidf-logreg" ? "the built-in labeller (TF-IDF, trained on synthetic data)" : name;
}

function RunStatus({ run, startedHere }: { run: ProcessRun; startedHere: boolean }) {
  if (run.status === "queued") return <p>Starting.</p>;
  if (run.status === "running") {
    return (
      <p>
        {run.to_label > 0
          ? `Labelling ${count(run.to_label, "new comment")} and rebuilding the issues`
          : "No new comments to label. Rebuilding the issues"}
        {run.started_at ? `, started ${dateTime(run.started_at)}` : ""}.
        {run.labeller === "tfidf-logreg" && " This usually takes under a minute."}
        {" "}This page updates when it finishes.
      </p>
    );
  }
  if (run.status === "failed") {
    return (
      <p className="notice notice-error">
        The last run failed{run.finished_at ? ` at ${dateTime(run.finished_at)}` : ""}: {run.error ?? "no reason given"}.
        Labels saved before the failure are kept. Try again, or ask the person who runs the server to check its log.
      </p>
    );
  }
  return (
    <div className={startedHere ? "notice" : undefined}>
      <p className={startedHere ? undefined : "muted small"}>
        {startedHere ? "Done" : "Last processed"}
        {run.finished_at ? ` ${dateTime(run.finished_at)}` : ""}.{" "}
        {run.labelled > 0
          ? `Labelled ${count(run.labelled, "comment")}${run.labeller ? ` with ${labellerName(run.labeller)}` : ""}, then grouped`
          : "No new comments to label. Grouped"}{" "}
        {count(run.comments_used ?? 0, "comment")} into {count(run.issues ?? 0, "issue")}.
        {run.failed_batches > 0 && ` ${count(run.failed_batches, "batch", "batches")} could not be labelled and will be tried again next run.`}
      </p>
      {startedHere && (
        <p>
          <Link to="/issues">See the updated issues</Link>
        </p>
      )}
    </div>
  );
}

export function ProcessPanel({ waiting, onStart, onDone, initial }: {
  /** Called when a run is started here. */
  onStart?: (run: ProcessRun) => void;
  /** Comments not yet in any issue, to say on the button what it will do. */
  waiting?: number;
  /** Called when a run started or watched here finishes, so the page can reload its numbers. */
  onDone?: (run: ProcessRun) => void;
  /** The latest run if the page already has it, to save a request. */
  initial?: ProcessRun | null;
}) {
  const [run, setRun] = useState<ProcessRun | null>(initial ?? null);
  const [loaded, setLoaded] = useState(initial !== undefined);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [startError, setStartError] = useState<unknown>(null);
  const [starting, setStarting] = useState(false);
  const [startedHere, setStartedHere] = useState(false);
  const watched = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (initial !== undefined) return;
    let current = true;
    api.latestRun().then(
      (out) => { if (current) { setRun(out.run); setLoaded(true); } },
      (cause: unknown) => { if (current) { setLoadError(cause); setLoaded(true); } },
    );
    return () => { current = false; };
  }, [initial]);

  // Poll while a run is going. Stops on its own once the run is done or failed.
  const runId = run?.id;
  const running = active(run);
  useEffect(() => {
    if (!running) return;
    watched.current = true;
    let current = true;
    const timer = window.setInterval(() => {
      api.latestRun().then(
        (out) => {
          if (!current || !out.run) return;
          setRun(out.run);
          if (!active(out.run)) onDoneRef.current?.(out.run);
        },
        (cause: unknown) => { if (current) setLoadError(cause); },
      );
    }, POLL_MS);
    return () => { current = false; window.clearInterval(timer); };
  }, [running, runId]);

  async function start() {
    if (starting || running) return;
    setStarting(true);
    setStartError(null);
    setLoadError(null);
    try {
      const started = await api.startRun();
      setRun(started);
      setStartedHere(true);
      onStart?.(started);
    } catch (cause) {
      setStartError(cause);
      // Someone else's run is going: show it and follow it.
      if (cause instanceof ApiError && cause.status === 409) {
        api.latestRun().then((out) => setRun(out.run), () => undefined);
      }
    } finally {
      setStarting(false);
    }
  }

  const busy = starting || running;
  return (
    <div className="process-panel">
      <div className="process-action">
        <button type="button" className="btn btn-primary" onClick={start} disabled={busy}
          aria-describedby="process-help">
          {busy ? "Processing" : "Process new feedback"}
        </button>
        <p id="process-help" className="muted small">
          {waiting !== undefined && waiting > 0
            ? `Labels the comments that have no labels yet and regroups all comments into issues. ${count(waiting, "comment")} waiting.`
            : "Labels the comments that have no labels yet and regroups all comments into issues."}
        </p>
      </div>
      <ErrorNotice error={startError} />
      <ErrorNotice error={loadError} />
      <div role="status" aria-live="polite">
        {loaded && run && <RunStatus run={run} startedHere={startedHere || (watched.current && !active(run))} />}
      </div>
    </div>
  );
}
