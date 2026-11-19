import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, STAGES, type Decision, type Stage, type Suggestion, type SuggestionStatus } from "./api";
import { dateTime, words } from "./format";
import { ErrorNotice } from "./states";

interface Props {
  suggestion: Suggestion;
  onDecided: (updated: Suggestion) => void;
  /** Hide the issue link when the card is already on that issue's page. */
  showIssue?: boolean;
}

const STATUS_TEXT: Record<SuggestionStatus, string> = {
  suggested: "Waiting for a decision",
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

/**
 * One suggestion, laid out to scan: the change as the heading, then owner, stage and
 * measure, then the quoted passages it rests on, then the decision (FR7, NFR2).
 */
export function SuggestionCard({ suggestion: s, onDecided, showIssue = true }: Props) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [changing, setChanging] = useState(false);
  const [change, setChange] = useState(s.change);
  const [owner, setOwner] = useState(s.owner);
  const [stage, setStage] = useState<string>(s.stage);
  const [measure, setMeasure] = useState(s.measure);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [last, setLast] = useState<Decision | null>(null);
  // After a decision the buttons go away, so focus moves to the line that says what happened.
  const outcome = useRef<HTMLParagraphElement>(null);
  const moveFocus = useRef(false);
  const decided = s.status !== "suggested";

  useEffect(() => {
    if (!moveFocus.current) return;
    moveFocus.current = false;
    outcome.current?.focus();
  });

  async function send(decision: Decision) {
    setBusy(true);
    setError(null);
    setLast(decision);
    try {
      const updated = await api.decide(s.id, decision);
      setEditing(false);
      setChanging(false);
      setChange(updated.change);
      setOwner(updated.owner);
      setStage(updated.stage);
      setMeasure(updated.measure);
      moveFocus.current = true;
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

  const retry = last ? () => void send(last) : undefined;
  const showActions = !editing && (!decided || changing);

  return (
    <article className="card suggestion" aria-labelledby={`${id}-title`}>
      <p className="suggestion-meta">
        <span className="muted small">Suggestion {s.id}</span>
        <span className={`badge ${STATUS_BADGE[s.status]}`}>{STATUS_TEXT[s.status]}</span>
      </p>
      <h3 id={`${id}-title`} className="suggestion-change">{s.change}</h3>
      {showIssue && (
        <p className="small">
          For issue <Link to={`/issues/${s.issue.id}`}>{s.issue.name}</Link>
        </p>
      )}

      {!editing && (
        <dl className="fields">
          <dt>Owner</dt>
          <dd>{s.owner}</dd>
          <dt>Stage of care</dt>
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
            <label htmlFor={`${id}-stage`}>Stage of care</label>
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
          <ErrorNotice error={error} onRetry={retry} />
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Saving" : "Save edit"}
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
        <ul className="citations">
          {s.citations.map((c, i) => (
            <li key={`${c.passage_id}-${i}`}>
              <blockquote>{c.quote}</blockquote>
              <p className="citation-source small">
                <cite>{c.title}</cite>
                {c.heading ? `, ${c.heading}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}

      <div className="decision">
        <p ref={outcome} tabIndex={-1} className={decided ? "decision-outcome" : "small muted"}>
          {decided
            ? `${STATUS_TEXT[s.status]} by ${s.decided_by ?? "unknown"}${s.decided_at ? `, ${dateTime(s.decided_at)}` : ""}.`
            : "Accept it as written, edit it first, or reject it. Every decision is logged."}
        </p>

        {!editing && <ErrorNotice error={error} onRetry={retry} />}

        {showActions && (
          <div className="actions" role="group" aria-label={`Decision on suggestion ${s.id}`}>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => send({ decision: "accept" })}>
              {busy && last?.decision === "accept" ? "Accepting" : "Accept"}
            </button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => { setError(null); setEditing(true); }}>
              Edit
            </button>
            <button type="button" className="btn btn-danger" disabled={busy} onClick={() => send({ decision: "reject" })}>
              {busy && last?.decision === "reject" ? "Rejecting" : "Reject"}
            </button>
            {decided && (
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => setChanging(false)}>
                Cancel
              </button>
            )}
          </div>
        )}
        {decided && !changing && !editing && (
          <div className="actions">
            <button type="button" className="btn btn-secondary btn-small" onClick={() => { setError(null); setChanging(true); }}>
              Change decision
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
