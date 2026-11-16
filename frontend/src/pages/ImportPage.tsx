import { useState, type FormEvent } from "react";
import { api, type ImportOut } from "../api";
import { ErrorNotice } from "../states";

export function ImportPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ImportOut | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const file = new FormData(form).get("file");
    setResult(null);
    setError(null);
    if (!(file instanceof File) || !file.size) {
      setError(new Error("Choose a CSV file that is not empty."));
      return;
    }
    setBusy(true);
    try {
      setResult(await api.importFeedback(file));
      form.reset();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="intake-page">
      <div className="page-head">
        <h1>Upload feedback CSV</h1>
        <p className="muted">Use synthetic, public, or de-identified feedback.</p>
      </div>
      <form className="panel intake-form" onSubmit={submit}>
        <fieldset disabled={busy}>
          <div className="field">
            <label htmlFor="import-file">CSV file</label>
            <input id="import-file" name="file" type="file" accept=".csv,text/csv" required
              aria-describedby="import-help" onChange={() => { setError(null); setResult(null); }} />
          </div>
          <div id="import-help" className="small muted">
            <p>Use a UTF-8 CSV up to 5 MB and 20,000 rows. Include these column headers:</p>
            <dl className="fields">
              <dt>text</dt><dd>The feedback comment</dd>
              <dt>source</dt><dd>patient, family, staff, nurse, or physician</dd>
              <dt>unit</dt><dd>A Kaizen unit code, such as 4B</dd>
              <dt>date</dt><dd>YYYY-MM-DD</dd>
            </dl>
          </div>
          <ErrorNotice error={error} />
          <button type="submit" className="btn btn-primary">Upload CSV</button>
        </fieldset>
        <div role="status">
          {busy && <p>Uploading and checking the CSV.</p>}
          {result && (
            <p className="notice">Batch {result.batch_id}: {result.saved} saved, {result.rejected} rejected.</p>
          )}
        </div>
      </form>
      {!!result?.errors.length && (
        <section aria-labelledby="import-errors">
          <h2 id="import-errors">Rejected rows</h2>
          {result.rejected > result.errors.length && (
            <p>Showing the first {result.errors.length} of {result.rejected} rejected rows.</p>
          )}
          <p>To avoid duplicates, upload only the rejected rows after fixing them.</p>
          <div className="table-wrap" tabIndex={0} aria-labelledby="import-errors-caption">
            <table className="data-table">
              <caption id="import-errors-caption">Rows skipped during import</caption>
              <thead><tr><th scope="col" className="num">Line</th><th scope="col">Reason</th></tr></thead>
              <tbody>
                {result.errors.map(({ line, reason }) => (
                  <tr key={line}><th scope="row" className="num">{line}</th><td>{reason}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </section>
  );
}
