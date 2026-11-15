import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, getToken, onUnauthorized, type Me } from "./api";

interface AuthState {
  me: Me | null;
  /** True until the stored token has been checked against /me. */
  checking: boolean;
  /** True when the API rejected the token mid-session, so the login page can say why. */
  expired: boolean;
  /** Set when the stored token could not be checked for a reason other than 401. */
  startupError: unknown;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState(() => getToken() !== null);
  const [expired, setExpired] = useState(false);
  const [startupError, setStartupError] = useState<unknown>(null);

  // Any 401 on a request that carried a token: forget the user. RequireLogin in App.tsx
  // then sends them to /login and back to the same page afterwards.
  useEffect(() => {
    onUnauthorized(() => {
      setMe(null);
      setExpired(true);
    });
    return () => onUnauthorized(null);
  }, []);

  // A token left in sessionStorage from before a reload: ask the API who it belongs to.
  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then(setMe)
      .catch((e) => {
        setMe(null);
        // A 401 is handled by onUnauthorized above. Anything else (API down, server
        // error) is shown instead of a login form that cannot work either.
        if (!(e instanceof ApiError && e.status === 401)) setStartupError(e);
      })
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await api.login(username, password);
    setMe(await api.me());
    setExpired(false);
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setMe(null);
    setExpired(false);
  }, []);

  return (
    <AuthContext.Provider value={{ me, checking, expired, startupError, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth needs an AuthProvider above it");
  return state;
}

/** QI staff and admins can draft and decide suggestions. Managers cannot (FR7). */
export function canReviewSuggestions(me: Me | null): boolean {
  return me?.role === "qi" || me?.role === "admin";
}
