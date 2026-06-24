"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";

interface AuthContextType {
  user: { id: number; username: string; is_superuser?: boolean; role?: "user" | "teacher" } | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthContextType["user"]>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/python/api/me", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok) setUser(data.user);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (data.ok) {
      setUser(data.user);
      return { ok: true };
    }
    return { ok: false, error: data.error || "Login failed" };
  }

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    setUser(null);
    window.location.href = "/login";
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}
