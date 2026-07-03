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
  const { login, verifyMfa } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Второй шаг (2FA через Telegram)
  const [mfa, setMfa] = useState<{ challengeId: string; hint?: string } | null>(null);
  const [code, setCode] = useState("");
  const [trust, setTrust] = useState(false);

  function goNext() {
    router.push(params.get("from") || "/");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const result = await login(username, password);
    setBusy(false);
    if (result.ok && result.mfa_required) {
      setMfa({ challengeId: result.challenge_id!, hint: result.telegram_hint });
      setCode("");
    } else if (result.ok) {
      goNext();
    } else {
      setError(result.error || "Login failed");
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!mfa) return;
    setError("");
    setBusy(true);
    const result = await verifyMfa(mfa.challengeId, code, trust);
    setBusy(false);
    if (result.ok) {
      goNext();
    } else {
      const left = result.attempts_left;
      setError(result.error + (typeof left === "number" ? ` (осталось попыток: ${left})` : ""));
      if (typeof left === "number" && left <= 0) {
        setMfa(null); // челлендж исчерпан — вернуться к вводу пароля
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="panel w-full max-w-md">
        <h1 className="text-2xl font-bold mb-2">NetRunner</h1>
        {!mfa ? (
          <>
            <p className="text-sm text-gray-500 mb-6">Вход в панель управления</p>
            <form onSubmit={handleSubmit} className="grid gap-4">
              <label className="label">
                Пользователь
                <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
              </label>
              <label className="label">
                Пароль
                <input
                  className="input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button className="btn w-full" disabled={busy}>
                {busy ? "Вход..." : "Войти"}
              </button>
            </form>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-500 mb-1">Подтверждение входа</p>
            <p className="text-sm mb-6">
              Мы отправили одноразовый код в Telegram
              {mfa.hint ? (
                <>
                  {" "}
                  (<b>{mfa.hint}</b>)
                </>
              ) : null}
              . Введите его, чтобы войти.
            </p>
            <form onSubmit={handleVerify} className="grid gap-4">
              <label className="label">
                Код из Telegram
                <input
                  className="input tracking-[0.4em] text-center text-lg"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="000000"
                  autoFocus
                  required
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
                <input type="checkbox" checked={trust} onChange={(e) => setTrust(e.target.checked)} />
                Доверять этому устройству 1 час (не спрашивать код)
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button className="btn w-full" disabled={busy}>
                {busy ? "Проверка..." : "Подтвердить вход"}
              </button>
              <button
                type="button"
                className="text-sm text-gray-500 hover:underline"
                onClick={() => {
                  setMfa(null);
                  setError("");
                }}
              >
                ← Назад к вводу пароля
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
