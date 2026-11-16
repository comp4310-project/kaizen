import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import { ErrorNotice } from "../states";

export function LoginPage() {
  const { me, expired, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/issues";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to={from} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    // The button stays enabled so people can find out what is missing.
    if (!username || !password) {
      setError(new Error("Enter your username and password."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  // On this page a 401 means a wrong username or password, not an ended login.
  const wrongPassword = error instanceof ApiError && error.status === 401;

  return (
    <section className="login panel">
      <h1>Kaizen</h1>
      <p className="muted">Recurring issues from patient or family and staff feedback. Log in with your Kaizen account.</p>
      {expired && !error && (
        <p className="notice" role="status">
          Your login ended. Log in again to carry on.
        </p>
      )}
      <form onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {wrongPassword ? (
          <p className="notice notice-error" role="alert">
            Wrong username or password.
          </p>
        ) : (
          <ErrorNotice error={error} />
        )}
        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? "Logging in" : "Log in"}
        </button>
      </form>
    </section>
  );
}
