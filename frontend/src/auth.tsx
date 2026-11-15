import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, type Me } from "./api";

interface AuthState {
  me: Me | null;
  /** True until the stored token has been checked against /me. */
  checking: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState(() => getToken() !== null);

  // A token left in sessionStorage from before a reload: ask the API who it belongs to.
  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await api.login(username, password);
    setMe(await api.me());
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setMe(null);
  }, []);

  return <AuthContext.Provider value={{ me, checking, login, logout }}>{children}</AuthContext.Provider>;
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
