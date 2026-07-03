"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useTheme } from "@/components/ThemeProvider";
import { useToast } from "@/components/Toast";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { LogOut, Sun, Moon, Send, Monitor, ShieldCheck, X } from "lucide-react";

interface TgStatus {
  configured: boolean;
  linked: boolean;
  username?: string | null;
  chat_id?: string | null;
}
interface TgLink {
  code: string;
  deep_link?: string | null;
  bot_username?: string | null;
  ttl_minutes?: number;
}
interface TrustedDevice {
  device_id: string;
  label?: string | null;
  trusted_until?: string | null; // null = бессрочно
  created_at: string;
  last_used_at?: string | null;
  current: boolean;
}

export default function AccountPage() {
  const { user, logout, refresh } = useAuth();
  const { theme, toggle } = useTheme();
  const showToast = useToast();

  const [username, setUsername] = useState("");
  const [savingName, setSavingName] = useState(false);

  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [savingPw, setSavingPw] = useState(false);

  const [tg, setTg] = useState<TgStatus | null>(null);
  const [tgLink, setTgLink] = useState<TgLink | null>(null);
  const [tgBusy, setTgBusy] = useState(false);

  const [devices, setDevices] = useState<TrustedDevice[] | null>(null);

  async function loadDevices() {
    try {
      const res = await apiGetClient("/api/me/devices");
      setDevices(res.devices || []);
    } catch {
      /* ignore */
    }
  }
  useEffect(() => {
    loadDevices();
  }, []);

  async function revokeDevice(device_id: string) {
    if (!confirm("Отозвать доверие к этому устройству? При следующем входе потребуется код.")) return;
    try {
      await apiPostClient("/api/me/devices/revoke", { device_id });
      await loadDevices();
      showToast("Устройство отозвано");
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }
  async function trustForever(device_id: string) {
    try {
      await apiPostClient("/api/me/devices/trust", { device_id, forever: true });
      await loadDevices();
      showToast("Устройство доверено бессрочно");
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function loadTg() {
    try {
      setTg(await apiGetClient("/api/me/telegram/status"));
    } catch {
      /* ignore */
    }
  }
  useEffect(() => {
    loadTg();
  }, []);

  // Пока ждём подтверждения привязки — опрашиваем статус.
  useEffect(() => {
    if (!tgLink || tg?.linked) return;
    const t = setInterval(async () => {
      try {
        const s: TgStatus = await apiGetClient("/api/me/telegram/status");
        setTg(s);
        if (s.linked) {
          setTgLink(null);
          showToast("Telegram привязан");
        }
      } catch {
        /* ignore */
      }
    }, 3000);
    return () => clearInterval(t);
  }, [tgLink, tg?.linked, showToast]);

  async function startTgLink() {
    setTgBusy(true);
    try {
      const res = await apiPostClient("/api/me/telegram/link", {});
      setTgLink(res);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setTgBusy(false);
    }
  }
  async function unlinkTg() {
    if (!confirm("Отвязать Telegram от аккаунта?")) return;
    setTgBusy(true);
    try {
      await apiPostClient("/api/me/telegram/unlink", {});
      setTgLink(null);
      await loadTg();
      showToast("Telegram отвязан");
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setTgBusy(false);
    }
  }

  useEffect(() => {
    if (user) setUsername(user.username);
  }, [user]);

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    setSavingName(true);
    try {
      await apiPostClient("/api/me/update", { username });
      showToast("Имя пользователя обновлено");
      await refresh();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setSavingName(false);
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      showToast("Новый пароль и подтверждение не совпадают", "error");
      return;
    }
    if (newPw.length < 4) {
      showToast("Новый пароль слишком короткий (минимум 4 символа)", "error");
      return;
    }
    setSavingPw(true);
    try {
      await apiPostClient("/api/me/update", { current_password: curPw, new_password: newPw });
      showToast("Пароль изменён");
      setCurPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setSavingPw(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-3xl font-bold">Профиль</h2>
        <p className="text-gray-500">Управление аккаунтом и оформлением</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Имя пользователя</h3>
        <form onSubmit={saveName} className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <label className="label flex-1">
            Имя
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
          <button className="btn" type="submit" disabled={savingName}>
            Сохранить
          </button>
        </form>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Смена пароля</h3>
        <form onSubmit={savePassword} className="grid gap-4 md:grid-cols-3">
          <label className="label">
            Текущий пароль
            <input className="input" type="password" value={curPw} onChange={(e) => setCurPw(e.target.value)} required />
          </label>
          <label className="label">
            Новый пароль
            <input className="input" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} required />
          </label>
          <label className="label">
            Подтверждение
            <input
              className="input"
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
            />
          </label>
          <div className="md:col-span-3">
            <button className="btn" type="submit" disabled={savingPw}>
              Изменить пароль
            </button>
          </div>
        </form>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Оформление</h3>
        <div className="flex items-center justify-between gap-4">
          <div className="text-sm text-gray-500">
            Тема интерфейса: <b>{theme === "dark" ? "тёмная" : "светлая"}</b>
          </div>
          <button type="button" className="btn-secondary" onClick={toggle}>
            {theme === "dark" ? (
              <>
                <Sun size={16} /> Светлая тема
              </>
            ) : (
              <>
                <Moon size={16} /> Тёмная тема
              </>
            )}
          </button>
        </div>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Telegram</h3>
        {!tg ? (
          <p className="text-sm text-gray-500">Загрузка…</p>
        ) : !tg.configured ? (
          <p className="text-sm text-gray-500">Telegram-бот не настроен администратором.</p>
        ) : tg.linked ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm">
              <span className="text-green-500">✓ Привязан</span>
              {tg.username ? <> : @{tg.username}</> : null}
              <span className="text-gray-500"> (chat {tg.chat_id})</span>
            </div>
            <button className="btn-secondary text-red-600" onClick={unlinkTg} disabled={tgBusy}>
              Отвязать
            </button>
          </div>
        ) : tgLink ? (
          <div className="space-y-2 text-sm">
            <p>Откройте бота и нажмите «Start», либо отправьте ему команду:</p>
            <code className="block bg-slate-950 text-gray-200 p-2 rounded select-all">/start {tgLink.code}</code>
            {tgLink.deep_link && (
              <a href={tgLink.deep_link} target="_blank" rel="noopener noreferrer" className="btn inline-flex">
                <Send size={16} /> Открыть бота {tgLink.bot_username ? `@${tgLink.bot_username}` : ""}
              </a>
            )}
            <p className="text-xs text-gray-500">
              Код действует {tgLink.ttl_minutes ?? 10} мин. Ожидаю подтверждения…
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-gray-500">Привяжите Telegram для подтверждения входа (2FA).</p>
            <button className="btn" onClick={startTgLink} disabled={tgBusy}>
              <Send size={16} /> Привязать Telegram
            </button>
          </div>
        )}
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-1 flex items-center gap-2">
          <ShieldCheck size={18} className="text-gray-400" /> Доверенные устройства
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          На этих устройствах вход не запрашивает код из Telegram (в пределах срока доверия).
        </p>
        {devices === null ? (
          <p className="text-sm text-gray-500">Загрузка…</p>
        ) : devices.length === 0 ? (
          <p className="text-sm text-gray-500">Доверенных устройств пока нет.</p>
        ) : (
          <ul className="space-y-2">
            {devices.map((d) => (
              <li
                key={d.device_id}
                className="flex flex-wrap items-center justify-between gap-3 border border-gray-200 dark:border-gray-700 rounded-lg p-3"
              >
                <div className="flex items-center gap-3 text-sm">
                  <Monitor size={18} className="text-gray-400 shrink-0" />
                  <div>
                    <div className="font-medium">
                      {d.label || "Устройство"}
                      {d.current && <span className="ml-2 text-xs text-green-500">(текущее)</span>}
                    </div>
                    <div className="text-xs text-gray-500">
                      {d.trusted_until === null ? (
                        <span className="text-amber-500">доверено бессрочно</span>
                      ) : (
                        <>доверие до {new Date(d.trusted_until!).toLocaleString("ru-RU")}</>
                      )}
                      {d.last_used_at && <> · был {new Date(d.last_used_at).toLocaleString("ru-RU")}</>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {d.trusted_until !== null && (
                    <button
                      className="btn-secondary text-xs"
                      onClick={() => trustForever(d.device_id)}
                      title="Не спрашивать код на этом устройстве никогда (небезопасно)"
                    >
                      Доверять всегда
                    </button>
                  )}
                  <button
                    className="btn-secondary text-red-600 text-xs"
                    onClick={() => revokeDevice(d.device_id)}
                  >
                    <X size={14} /> Отозвать
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="panel">
        <button onClick={logout} className="btn-danger w-full justify-center">
          <LogOut size={16} /> Выйти из аккаунта
        </button>
      </div>
    </div>
  );
}
