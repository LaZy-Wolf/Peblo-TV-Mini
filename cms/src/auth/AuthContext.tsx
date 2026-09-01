import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { SESSION_EXPIRED_EVENT, api, getToken, setToken } from "../api/client";

type Session = { email: string; role: string };

type AuthValue = {
  token: string | null;
  email: string | null;
  role: string | null;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);
const SESSION_KEY = "peblo.cms.session";

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken());
  const [session, setSession] = useState<Session | null>(readSession());

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.post<{ access_token: string; role: string; email: string }>(
      "/auth/login",
      { email, password },
    );
    setToken(result.access_token);
    setTokenState(result.access_token);
    const next = { email: result.email, role: result.role };
    localStorage.setItem(SESSION_KEY, JSON.stringify(next));
    setSession(next);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }, []);

  // Any 401 from the API means this session is over. Drop straight back to
  // the login screen instead of leaving a dead page behind.
  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, logout);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, logout);
  }, [logout]);

  const value = useMemo<AuthValue>(
    () => ({
      token,
      email: session?.email ?? null,
      role: session?.role ?? null,
      // The server enforces this. The flag only decides what to render, so a
      // tampered value gets a 403 rather than access.
      isAdmin: session?.role === "admin",
      login,
      logout,
    }),
    [token, session, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
