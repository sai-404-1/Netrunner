"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useTheme } from "@/components/ThemeProvider";
import { useToast } from "@/components/Toast";
import { apiPostClient } from "@/lib/api-client";
import { LogOut, Sun, Moon } from "lucide-react";

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
        <button onClick={logout} className="btn-danger w-full justify-center">
          <LogOut size={16} /> Выйти из аккаунта
        </button>
      </div>
    </div>
  );
}
