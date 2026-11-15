import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { api, CATEGORIES, STAGES, type IssueComment, type IssueCommentsOut, type IssueSummary, type LabelsIn } from "./api";
import { words } from "./format";
import { ErrorNotice } from "./states";

type LabelValues = Required<LabelsIn>;
const sentiments = ["positive", "neutral", "negative"] as const;
const urgencies = ["low", "medium", "high"] as const;

// Textareas normalize line breaks and return UTF-16 offsets. Python slices code points
// in the original string, so count each original character covered by the selection.
function originalOffset(text: string, offset: number): number | null {
  let position = 0;
  let original = 0;
  for (const [character] of text.matchAll(/\r\n|[\s\S]/gu)) {
    if (position === offset) return original;
    position += character === "\r\n" ? 1 : character.length;
    original += character === "\r\n" ? 2 : 1;
  }
  return position === offset ? original : null;
}

export function CommentReview({ comment, onUpdate }: {
  comment: IssueComment;
  onUpdate: (id: number, changes: Partial<Pick<IssueComment, "text" | "labels">>) => void;
}) {
  const id = useId();
  const [mode, setMode] = useState<"labels" | "redact" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState("");
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const text = comment.text.replace(/\r\n?/g, "\n");

  function open(next: typeof mode) {
    setError(null);
    setNote("");
    setSelection({ start: 0, end: 0 });
    setMode(next);
  }

  async function save(action: () => Promise<void>, success: string) {
    setBusy(true);
    setError(null);
    setNote("");
    try {
      await action();
      setMode(null);
      setNote(success);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  function confirm(labels: LabelsIn) {
    void save(async () => {
      const updated = await api.confirmLabels(comment.id, labels);
      onUpdate(comment.id, { labels: updated });
    }, "Labels confirmed.");
  }

  function redact(event: FormEvent) {
    event.preventDefault();
    const start = originalOffset(comment.text, selection.start);
    const end = originalOffset(comment.text, selection.end);
    if (start === null || end === null || start >= end) {
      setError(new Error("Select the full text you want to redact."));
      return;
    }
    void save(async () => {
      const updated = await api.redactComment(comment.id, start, end);
      onUpdate(comment.id, { text: updated.text });
    }, "Selected text redacted.");
  }

  return (
    <div className="review-controls">
      <ErrorNotice error={error} />
      <p role="status" className="small">{note}</p>
      {mode === null && (
        <div className="review-actions">
          {comment.labels?.status === "suggested" && (
            <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => confirm({})}>
              {busy ? "Confirming" : "Confirm labels"}
            </button>
          )}
          {comment.labels && (
            <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => open("labels")}>
              Edit labels
            </button>
          )}
          <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => open("redact")}>
            Redact
          </button>
        </div>
      )}
      {mode === "labels" && comment.labels && (
        <form onSubmit={(event) => {
          event.preventDefault();
          const fields = new FormData(event.currentTarget);
          const next: LabelValues = {
            sentiment: fields.get("sentiment") as LabelValues["sentiment"],
            stage: fields.get("stage") as LabelValues["stage"],
            urgency: fields.get("urgency") as LabelValues["urgency"],
            categories: fields.getAll("categories") as LabelValues["categories"],
          };
          const previous = comment.labels!;
          const changed: LabelsIn = {};
          if (next.sentiment !== previous.sentiment) changed.sentiment = next.sentiment;
          if (next.stage !== previous.stage) changed.stage = next.stage;
          if (next.urgency !== previous.urgency) changed.urgency = next.urgency;
          if (next.categories.length !== previous.categories.length || next.categories.some((c) => !previous.categories.includes(c))) {
            changed.categories = next.categories;
          }
          confirm(changed);
        }}>
          <fieldset disabled={busy}>
            <legend>Edit labels for comment {comment.id}</legend>
            <div className="review-actions">
              <LabelSelect id={id} name="sentiment" label="Sentiment" value={comment.labels.sentiment} choices={sentiments} />
              <LabelSelect id={id} name="stage" label="Stage of care" value={comment.labels.stage} choices={STAGES} />
              <LabelSelect id={id} name="urgency" label="Urgency" value={comment.labels.urgency} choices={urgencies} />
            </div>
            <fieldset className="review-categories">
              <legend>Categories</legend>
              {CATEGORIES.map((category) => (
                <div key={category}>
                  <input type="checkbox" id={id + category} name="categories" value={category}
                    defaultChecked={comment.labels?.categories.includes(category)} />
                  <label htmlFor={id + category}>{words(category)}</label>
                </div>
              ))}
            </fieldset>
            <div className="review-actions">
              <button type="submit" className="btn btn-primary">{busy ? "Saving" : "Save and confirm"}</button>
              <button type="button" className="btn btn-secondary" onClick={() => open(null)}>Cancel</button>
            </div>
          </fieldset>
        </form>
      )}
      {mode === "redact" && (
        <form onSubmit={redact}>
          <div className="field">
            <label htmlFor={id + "redact"}>Select the text to redact</label>
            <textarea id={id + "redact"} rows={4} readOnly value={text} onSelect={(event) => {
              setSelection({ start: event.currentTarget.selectionStart, end: event.currentTarget.selectionEnd });
            }} />
          </div>
          {selection.start < selection.end && (
            <p className="comment-text">Selected text: <mark>{text.slice(selection.start, selection.end)}</mark></p>
          )}
          <div className="review-actions">
            <button type="submit" className="btn btn-danger" disabled={busy}>{busy ? "Redacting" : "Confirm redaction"}</button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => open(null)}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}

function LabelSelect({ id, name, label, value, choices }: {
  id: string; name: string; label: string; value: string; choices: readonly string[];
}) {
  return (
    <div className="field">
      <label htmlFor={id + name}>{label}</label>
      <select id={id + name} name={name} defaultValue={value}>
        {choices.map((choice) => <option key={choice} value={choice}>{words(choice)}</option>)}
      </select>
    </div>
  );
}

export function IssueReview({ issue, onRename, onMerge }: {
  issue: IssueCommentsOut["issue"];
  onRename: (issue: IssueCommentsOut["issue"]) => void;
  onMerge: (id: number) => void;
}) {
  const [mode, setMode] = useState<"rename" | "merge" | null>(null);
  const [name, setName] = useState(issue.name);
  const [into, setInto] = useState("");
  const [targets, setTargets] = useState<IssueSummary[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    if (mode !== "merge") return;
    let current = true;
    api.issues(200).then(
      (out) => {
        if (current) setTargets(out.issues.some((row) => row.id === issue.id)
          ? out.issues.filter((row) => row.id !== issue.id)
          : []);
      },
      (cause: unknown) => { if (current) setError(cause); },
    );
    return () => { current = false; };
  }, [issue.id, mode]);

  function open(next: typeof mode) {
    setName(issue.name);
    setInto("");
    setTargets(null);
    setError(null);
    setNote("");
    setMode(next);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (mode === "rename" && !name.trim()) {
      setError(new Error("Enter a name for this issue."));
      return;
    }
    if (mode === "merge" && !into) {
      setError(new Error("Choose an issue to keep."));
      return;
    }
    setBusy(true);
    try {
      if (mode === "rename") {
        onRename(await api.renameIssue(issue.id, name.trim()));
        setMode(null);
        setNote("Issue renamed.");
      } else {
        const merged = await api.mergeIssue(issue.id, Number(into));
        onMerge(merged.id);
      }
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="review-controls">
      <ErrorNotice error={error} />
      <p role="status" className="small">{note}</p>
      {mode === null ? (
        <div className="review-actions">
          <button type="button" className="btn btn-secondary" onClick={() => open("rename")}>Rename issue</button>
          <button type="button" className="btn btn-secondary" onClick={() => open("merge")}>Merge into another issue</button>
        </div>
      ) : (
        <form onSubmit={submit}>
          {mode === "rename" ? (
            <div className="field">
              <label htmlFor="issue-name">Issue name</label>
              <input id="issue-name" value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
            </div>
          ) : (
            <>
              {!targets && error === null && <p role="status">Loading merge targets.</p>}
              {targets?.length === 0 && <p>No other issue from this run is available to merge into.</p>}
              {!!targets?.length && (
                <>
                  <div className="field">
                    <label htmlFor="merge-target">Issue to keep</label>
                    <select id="merge-target" value={into} onChange={(event) => setInto(event.target.value)}>
                      <option value="">Choose an issue</option>
                      {targets.map((target) => <option key={target.id} value={target.id}>{target.name}</option>)}
                    </select>
                  </div>
                  <p>This issue will be deleted. Its comments and suggestions will move to the issue you keep.</p>
                </>
              )}
            </>
          )}
          <div className="review-actions">
            {(mode === "rename" || !!targets?.length) && (
              <button type="submit" className={mode === "rename" ? "btn btn-primary" : "btn btn-danger"} disabled={busy}>
                {busy ? "Saving" : mode === "rename" ? "Save name" : "Confirm merge"}
              </button>
            )}
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => open(null)}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}
