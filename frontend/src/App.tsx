import type { ReactNode } from "react";
import { Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { canReviewSuggestions, useAuth } from "./auth";
import { IssueDetailPage } from "./pages/IssueDetailPage";
import { IssuesPage } from "./pages/IssuesPage";
import { LoginPage } from "./pages/LoginPage";
import { SuggestionsPage } from "./pages/SuggestionsPage";

function RequireLogin({ children }: { children: ReactNode }) {
  const { me, checking } = useAuth();
  const location = useLocation();
  if (checking) return <p role="status">Checking your login...</p>;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

function Header() {
  const { me, logout } = useAuth();
  if (!me) return null;
  return (
    <header className="site-header">
      <nav aria-label="Main">
        <span className="brand">Kaizen</span>
        <NavLink to="/issues">Issues</NavLink>
        {canReviewSuggestions(me) && <NavLink to="/suggestions">Suggestions</NavLink>}
      </nav>
      <div className="who">
        <span>
          {me.username} ({me.role}
          {me.unit ? `, unit ${me.unit}` : ""})
        </span>
        <button type="button" className="secondary" onClick={logout}>
          Log out
        </button>
      </div>
    </header>
  );
}

export function App() {
  const { me } = useAuth();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
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
            path="/suggestions"
            element={
              <RequireLogin>
                {canReviewSuggestions(me) ? <SuggestionsPage /> : <Navigate to="/issues" replace />}
              </RequireLogin>
            }
          />
          <Route path="*" element={<Navigate to="/issues" replace />} />
        </Routes>
      </main>
    </>
  );
}
