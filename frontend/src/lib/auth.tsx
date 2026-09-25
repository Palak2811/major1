"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, refreshSession, setAccessToken, setOnAuthLost } from "./api";
import type { Role, TokenOut, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (full_name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<boolean>;
  can: (scope: string) => boolean;
  hasRole: (...roles: Role[]) => boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    const ok = await refreshSession();
    if (ok) {
      try {
        setUser(await api<User>("/auth/me"));
      } catch {
        setUser(null);
      }
    } else {
      setUser(null);
    }
    setLoading(false);
    return ok;
  }, []);

  useEffect(() => {
    setOnAuthLost(() => setUser(null));
    void bootstrap();
  }, [bootstrap]);

  const accept = (t: TokenOut) => {
    setAccessToken(t.access_token);
    setUser(t.user);
  };

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    bootstrap,
    login: async (email, password) => accept(await api<TokenOut>("/auth/login", { method: "POST", json: { email, password } })),
    register: async (full_name, email, password) =>
      accept(await api<TokenOut>("/auth/register", { method: "POST", json: { full_name, email, password } })),
    logout: async () => {
      await api("/auth/logout", { method: "POST" }).catch(() => undefined);
      setAccessToken(null);
      setUser(null);
    },
    can: (scope) => !!user?.scopes.includes(scope),
    hasRole: (...roles) => !!user && roles.includes(user.role),
  }), [user, loading, bootstrap]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
