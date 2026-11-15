import { useId, useState, type FormEvent } from "react";
import { api, STAGES, type Decision, type Stage, type Suggestion, type SuggestionStatus } from "./api";
import { dateTime, words } from "./format";
import { ErrorNotice } from "./states";

interface Props {
  suggestion: Suggestion;
  onDecided: (updated: Suggestion) => void;
  /** Hide the issue name when the card is already on that issue's page. */
  showIssue?: boolean;
}

const STATUS_TEXT: Record<SuggestionStatus, string> = {
  suggested: "Waiting",
  accepted: "Accepted",
  edited: "Edited",
  rejected: "Rejected",
};

const STATUS_BADGE: Record<SuggestionStatus, string> = {
  suggested: "badge-warn",
  accepted: "badge-ok",
  edited: "badge-ok",
  rejected: "badge-danger",
};

function isStage(value: string): value is Stage {
  return (STAGES as string[]).includes(value);
}

/** One suggestion with its citations, plus accept, edit and reject for QI staff (FR7, NFR2). */
export function SuggestionCard({ suggestion: s, onDecided, showIssue = true }: Props) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [change, setChange] = useState(s.change);
  const [owner, setOwner] = useState(s.owner);
  const [stage, setStage] = useState<string>(s.stage);
  const [measure, setMeasure] = useState(s.measure);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function send(decision: Decision) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.decide(s.id, decision);
      setEditing(false);
      onDecided(updated);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  // Only send the fields that changed: the API logs which fields were edited.
  function saveEdit(event: FormEvent) {
    event.preventDefault();
    const edit: Decision = { decision: "edit" };
    if (change.trim() !== s.change) edit.change = change.trim();
    if (owner.trim() !== s.owner) edit.owner = owner.trim();
    if (stage !== s.stage && isStage(stage)) edit.stage = stage;
    if (measure.trim() !== s.measure) edit.measure = measure.trim();
    if (Object.keys(edit).length === 1) {
      setError(new Error("Nothing has changed. Use Accept to keep it as it is."));
      return;
    }
    void send(edit);
  }

  function cancelEdit() {
    setChange(s.change);
    setOwner(s.owner);
    setStage(s.stage);
    setMeasure(s.measure);
    setError(null);
    setEditing(false);
  }

  return (
    <article className="card" aria-labelledby={`${id}-title`}>
      <header className="card-head">
        <h3 id={`${id}-title`}>Suggestion {s.id}</h3>
        <span className={`badge ${STATUS_BADGE[s.status]}`}>{STATUS_TEXT[s.status]}</span>
      </header>
      {showIssue && (
        <p className="muted small">
          Issue {s.issue.id}: {s.issue.name}
        </p>
      )}

      {!editing && (
        <dl className="fields">
          <dt>Change</dt>
          <dd>{s.change}</dd>
          <dt>Owner</dt>
          <dd>{s.owner}</dd>
          <dt>Stage</dt>
          <dd>{words(s.stage)}</dd>
          <dt>Measure</dt>
          <dd>{s.measure}</dd>
        </dl>
      )}

      {editing && (
        <form onSubmit={saveEdit} className="edit-form">
          <div className="field">
            <label htmlFor={`${id}-change`}>Change</label>
            <textarea id={`${id}-change`} rows={3} required value={change} onChange={(e) => setChange(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-owner`}>Owner</label>
            <input id={`${id}-owner`} maxLength={120} required value={owner} onChange={(e) => setOwner(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-stage`}>Stage</label>
            <select id={`${id}-stage`} value={stage} onChange={(e) => setStage(e.target.value)}>
              {!isStage(s.stage) && <option value={s.stage}>{words(s.stage)}</option>}
              {STAGES.map((value) => (
                <option key={value} value={value}>
                  {words(value)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-measure`}>Measure</label>
            <textarea id={`${id}-measure`} rows={2} required value={measure} onChange={(e) => setMeasure(e.target.value)} />
          </div>
          <ErrorNotice error={error} />
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              Save edit
            </button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={cancelEdit}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <h4>Citations</h4>
      {s.citations.length === 0 ? (
        <p className="muted small">No citations.</p>
      ) : (
        <ol className="citations">
          {s.citations.map((c, i) => (
            <li key={`${c.passage_id}-${i}`}>
              <blockquote>{c.quote}</blockquote>
              <p className="muted small">
                {c.title}
                {c.heading ? `, ${c.heading}` : ""}. Passage {c.passage_id}.
              </p>
            </li>
          ))}
        </ol>
      )}

      {s.status !== "suggested" && (
        <p className="muted small">
          {STATUS_TEXT[s.status]} by {s.decided_by ?? "unknown"}
          {s.decided_at ? `, ${dateTime(s.decided_at)}` : ""}.
        </p>
      )}

      {!editing && <ErrorNotice error={error} />}

      {!editing && (
        <div className="actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => send({ decision: "accept" })}>
            Accept
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => setEditing(true)}>
            Edit
          </button>
          <button type="button" className="btn btn-danger" disabled={busy} onClick={() => send({ decision: "reject" })}>
            Reject
          </button>
        </div>
      )}
    </article>
  );
}
