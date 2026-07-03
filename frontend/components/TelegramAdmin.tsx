"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { Send, Save } from "lucide-react";

/** Конфиг Telegram-бота NetRunner (только админ). Пользователи привязывают бота в кабинете. */
export function TelegramAdmin() {
  const showToast = useToast();
  const [status, setStatus] = useState<{ configured: boolean; bot_username?: string | null } | null>(null);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setStatus(await apiGetClient("/api/admin/telegram"));
    } catch (e: any) {
      showToast(e.message, "error");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await apiPostClient("/api/admin/telegram", { token });
      setStatus(res);
      setToken("");
      showToast(res.configured ? `Бот подключён${res.bot_username ? `: @${res.bot_username}` : ""}` : "Бот не настроен");
    } catch (e: any) {
      showToast(e.message, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Send size={18} className="text-gray-400" />
        <h3 className="font-semibold">Telegram-бот</h3>
      </div>
      {status && (
        <p className="text-sm">
          {status.configured ? (
            <span className="text-green-500">✓ Подключён{status.bot_username ? `: @${status.bot_username}` : ""}</span>
          ) : (
            <span className="text-gray-500">Не настроен</span>
          )}
        </p>
      )}
      <form onSubmit={save} className="flex flex-col md:flex-row md:items-end gap-3">
        <label className="label flex-1">
          Bot token (от @BotFather)
          <input
            className="input"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder={status?.configured ? "•••••• (пусто — не менять, «-» — очистить)" : "123456:ABC-DEF…"}
          />
        </label>
        <button className="btn-secondary shrink-0" type="submit" disabled={saving}>
          <Save size={16} /> {saving ? "Сохранение…" : "Сохранить"}
        </button>
      </form>
      <p className="text-xs text-gray-500">
        Нужен отдельный бот для NetRunner (не общий с другими сервисами). Пользователи привязывают его в личном кабинете.
      </p>
    </div>
  );
}
