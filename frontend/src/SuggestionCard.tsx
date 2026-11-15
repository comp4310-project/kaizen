import { useId, useState, type FormEvent } from "react";
import { api, STAGES, type Decision, type Stage, type Suggestion } from "./api";
import { errorText, words } from "./format";

interface Props {
  suggestion: Suggestion;
  onDecided: (updated: Suggestion) => void;
  /** Hide the issue name when the card is already on that issue's page. */
  showIssue?: boolean;
}

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
  const [error, setError] = useState<string | null>(null);

  async function send(decision: Decision) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.decide(s.id, decision);
      setEditing(false);
      onDecided(updated);
    } catch (e) {
      setError(errorText(e));
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
      setError("Nothing has changed. Use Accept to keep it as it is.");
      return;
    }
    void send(edit);
  }

  const decided = s.status !== "suggested";

  return (
    <article className="card" aria-labelledby={`${id}-title`}>
      <header className="card-head">
        <h3 id={`${id}-title`}>Suggestion {s.id}</h3>
        <span className={`tag status-${s.status}`}>{s.status}</span>
      </header>
      {showIssue && (
        <p className="muted">
          For issue {s.issue.id}: {s.issue.name}
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
          <label htmlFor={`${id}-change`}>Change</label>
          <textarea id={`${id}-change`} rows={3} required value={change} onChange={(e) => setChange(e.target.value)} />
          <label htmlFor={`${id}-owner`}>Owner</label>
          <input id={`${id}-owner`} maxLength={120} required value={owner} onChange={(e) => setOwner(e.target.value)} />
          <label htmlFor={`${id}-stage`}>Stage</label>
          <select id={`${id}-stage`} value={stage} onChange={(e) => setStage(e.target.value)}>
            {!isStage(s.stage) && <option value={s.stage}>{words(s.stage)}</option>}
            {STAGES.map((value) => (
              <option key={value} value={value}>
                {words(value)}
              </option>
            ))}
          </select>
          <label htmlFor={`${id}-measure`}>Measure</label>
          <textarea id={`${id}-measure`} rows={2} required value={measure} onChange={(e) => setMeasure(e.target.value)} />
          <div className="actions">
            <button type="submit" disabled={busy}>
              Save edit
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <h4>Citations</h4>
      {s.citations.length === 0 ? (
        <p className="muted">No citations.</p>
      ) : (
        <ol className="citations">
          {s.citations.map((c, i) => (
            <li key={`${c.passage_id}-${i}`}>
              <blockquote>{c.quote}</blockquote>
              <p className="muted">
                {c.title}
                {c.heading ? `, ${c.heading}` : ""} (passage {c.passage_id})
              </p>
            </li>
          ))}
        </ol>
      )}

      {decided && (
        <p className="muted">
          {s.status} by {s.decided_by ?? "unknown"}
          {s.decided_at ? ` on ${new Date(s.decided_at).toLocaleString()}` : ""}
        </p>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {!editing && (
        <div className="actions">
          <button type="button" disabled={busy} onClick={() => send({ decision: "accept" })}>
            Accept
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setEditing(true)}>
            Edit
          </button>
          <button type="button" className="danger" disabled={busy} onClick={() => send({ decision: "reject" })}>
            Reject
          </button>
        </div>
      )}
    </article>
  );
}
