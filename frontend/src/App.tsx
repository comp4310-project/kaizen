import { useEffect, useRef, type ReactNode } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { canReviewSuggestions, useAuth } from "./auth";
import { roleName } from "./format";
import { CommentsPage } from "./pages/CommentsPage";
import { ComparePage } from "./pages/ComparePage";
import { FeedbackPage } from "./pages/FeedbackPage";
import { ImportPage } from "./pages/ImportPage";
import { IssueDetailPage } from "./pages/IssueDetailPage";
import { IssuesPage } from "./pages/IssuesPage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SuggestionsPage } from "./pages/SuggestionsPage";
import { ErrorNotice } from "./states";

function RequireLogin({ children }: { children: ReactNode }) {
  const { me, checking, startupError } = useAuth();
  const location = useLocation();
  if (checking) return <p role="status">Checking your login.</p>;
  if (!me && startupError !== null) {
    return (
      <section>
        <h1>Kaizen</h1>
        <ErrorNotice error={startupError} />
        <button type="button" className="btn btn-secondary" onClick={() => window.location.reload()}>
          Try again
        </button>
      </section>
    );
  }
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

function Header() {
  const { me, checking, logout } = useAuth();
  // While a stored login is checked the links already work: each route waits for the check.
  if (checking) {
    return (
      <header className="site-header">
        <div className="container header-inner">
          <span className="brand">Kaizen</span>
          <nav aria-label="Main" className="nav">
            <NavLink to="/overview">Overview</NavLink>
            <NavLink to="/issues">Issues</NavLink>
            <NavLink to="/compare">Compare</NavLink>
          </nav>
          <div className="who muted">Checking your login</div>
        </div>
      </header>
    );
  }
  if (!me) return null;
  return (
    <header className="site-header">
      <div className="container header-inner">
        <span className="brand">Kaizen</span>
        <nav aria-label="Main" className="nav">
          <NavLink to="/overview">Overview</NavLink>
          <NavLink to="/issues">Issues</NavLink>
          <NavLink to="/compare">Compare</NavLink>
          {canReviewSuggestions(me) && <NavLink to="/suggestions">Suggestions</NavLink>}
          {canReviewSuggestions(me) && <NavLink to="/imports">Upload CSV</NavLink>}
          <NavLink to="/feedback">Send feedback</NavLink>
        </nav>
        <div className="who">
          <span className="who-name">{me.username}</span>
          <span className="who-role">
            {roleName(me.role)}
            {me.unit ? `, ${me.unit}` : ""}
          </span>
          <button type="button" className="btn btn-secondary btn-small" onClick={logout}>
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}

/**
 * On every route change, move focus to the page's h1, so keyboard and screen reader users
 * start in the same place however the page was opened (usability round 2). Not on the first
 * load, where the browser starts at the top anyway, and not for links to an #anchor. A page
 * that has no h1 yet gets a few frames to render one; after that focus goes to <main>.
 */
function useRouteFocus() {
  const { pathname, hash } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (hash) return;
    let frame = 0;
    let tries = 0;
    const focus = () => {
      const heading = document.querySelector<HTMLElement>("main h1");
      if (heading) {
        if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
        heading.focus();
      } else if (tries++ < 10) {
        frame = requestAnimationFrame(focus);
      } else {
        document.getElementById("main")?.focus();
      }
    };
    frame = requestAnimationFrame(focus);
    return () => cancelAnimationFrame(frame);
  }, [pathname, hash]);
}

/** Opening /login directly lands on the overview after login, unless a page sent the user here. */
function LoginRoute() {
  const location = useLocation();
  if (!(location.state as { from?: string } | null)?.from) {
    return <Navigate to="/login" replace state={{ from: "/overview" }} />;
  }
  return <LoginPage />;
}

export function App() {
  const { me } = useAuth();
  useRouteFocus();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main" tabIndex={-1} className="container">
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route
            path="/overview"
            element={
              <RequireLogin>
                <OverviewPage />
              </RequireLogin>
            }
          />
          <Route
            path="/comments"
            element={
              <RequireLogin>
                <CommentsPage />
              </RequireLogin>
            }
          />
          <Route path="/feedback" element={<FeedbackPage />} />
          <Route
            path="/imports"
            element={
              <RequireLogin>
                {canReviewSuggestions(me) ? <ImportPage /> : <Navigate to="/issues" replace />}
              </RequireLogin>
            }
          />
          <Route
            path="/issues"
            element={
              <RequireLogin>
                <IssuesPage />
              </RequireLogin>
            }
          />
          <Route
            path="/issues/:issueId"
            element={
              <RequireLogin>
                <IssueDetailPage />
              </RequireLogin>
            }
          />
          <Route
            path="/compare"
            element={
              <RequireLogin>
                <ComparePage />
              </RequireLogin>
            }
          />
          <Route
            path="/suggestions"
            element={
              <RequireLogin>
                {canReviewSuggestions(me) ? <SuggestionsPage /> : <Navigate to="/issues" replace />}
              </RequireLogin>
            }
          />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </main>
    </>
  );
}
