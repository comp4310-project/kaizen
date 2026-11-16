import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type Source, type Unit } from "../api";
import { useAuth } from "../auth";
import { sortUnits } from "../format";
import { EmptyState, ErrorNotice, SkeletonBlocks } from "../states";

export function FeedbackPage() {
  const { me } = useAuth();
  const [units, setUnits] = useState<Unit[] | null>(null);
  const [unitsError, setUnitsError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    let active = true;
    api.units().then(
      (result) => { if (active) setUnits(sortUnits(result)); },
      (cause: unknown) => { if (active) setUnitsError(cause); },
    );
    return () => { active = false; };
  }, [attempt]);

  function retryUnits() {
    setUnitsError(null);
    setAttempt((count) => count + 1);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    const text = String(fields.get("text") ?? "").trim();
    setError(null);
    setSent(false);
    if (!text) {
      setError(new Error("Enter your feedback."));
      form.querySelector("textarea")?.focus();
      return;
    }

    setBusy(true);
    try {
      await api.submitFeedback({
        text,
        source: fields.get("source") as Source,
        unit: String(fields.get("unit") ?? ""),
        date: String(fields.get("date") ?? "") || undefined,
      });
      form.reset();
      setSent(true);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="intake-page">
      <div className="page-head">
        <h1>Send feedback</h1>
        <p className="muted">Use fictional feedback for this prototype. Leave out names and identifying details.</p>
        {!me && <Link to="/login">Staff log in</Link>}
      </div>

      {unitsError !== null && (
        <>
          <ErrorNotice error={unitsError} />
          <button type="button" className="btn btn-secondary" onClick={retryUnits}>Reload units</button>
        </>
      )}
      {!units && unitsError === null && <SkeletonBlocks count={1} label="Loading units" />}
      {units?.length === 0 && <EmptyState>No units are available. Contact a Kaizen administrator.</EmptyState>}
      {!!units?.length && (
        <form className="panel intake-form" onSubmit={submit}>
          <fieldset disabled={busy}>
            <div className="field">
              <label htmlFor="feedback-source">Who is giving feedback?</label>
              <select id="feedback-source" name="source" required defaultValue="">
                <option value="" disabled>Choose a source</option>
                <option value="patient_family">Patient or family</option>
                <option value="staff">Staff</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="feedback-unit">Hospital unit</label>
              <select id="feedback-unit" name="unit" required defaultValue="">
                <option value="" disabled>Choose a unit</option>
                {units.map(({ code, name }) => <option key={code} value={code}>{code} ({name})</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="feedback-date">Date of feedback (optional)</label>
              <input id="feedback-date" name="date" type="date" aria-describedby="feedback-date-help" />
              <p id="feedback-date-help" className="muted small">Leave blank to use today.</p>
            </div>
            <div className="field">
              <label htmlFor="feedback-text">Your feedback</label>
              <textarea id="feedback-text" name="text" rows={5} required
                aria-describedby="feedback-text-help" />
              <p id="feedback-text-help" className="muted small">Up to 5,000 characters.</p>
            </div>
            <ErrorNotice error={error} />
            <button type="submit" className="btn btn-primary">Send feedback</button>
          </fieldset>
          <div role="status">
            {busy && <p>Sending feedback.</p>}
            {sent && <p className="notice">Thank you. Your feedback was received.</p>}
          </div>
        </form>
      )}
    </section>
  );
}
