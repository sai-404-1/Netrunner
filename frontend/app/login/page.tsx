"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center p-6">Загрузка...</div>}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const result = await login(username, password);
    setBusy(false);
    if (result.ok) {
      router.push(params.get("from") || "/");
    } else {
      setError(result.error || "Login failed");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="panel w-full max-w-md">
        <h1 className="text-2xl font-bold mb-2">NetRunner</h1>
        <p className="text-sm text-gray-500 mb-6">Вход в панель управления</p>
        <form onSubmit={handleSubmit} className="grid gap-4">
          <label className="label">
            Пользователь
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
          <label className="label">
            Пароль
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn w-full" disabled={busy}>
            {busy ? "Вход..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
