"use client";

import { useEffect, useState, useCallback } from "react";
import { useToast } from "@/components/Toast";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import {
  fetchExecutionSettings,
  saveExecutionSettings,
  type ExecutionField,
  type SshUserMode,
} from "@/lib/execution-settings";

export function AgentTab() {
  const showToast = useToast();

  const [defaultCreds, setDefaultCreds] = useState<{ username: string; has_password: boolean }>({ username: "", has_password: false });
  const [credsSaving, setCredsSaving] = useState(false);
  const [sshUserMode, setSshUserMode] = useState<SshUserMode>("service");
  const [sshUserField, setSshUserField] = useState<ExecutionField | null>(null);
  const [coldawnRetries, setColdawnRetries] = useState<number>(3);
  const [coldawnField, setColdawnField] = useState<ExecutionField | null>(null);
  const [execSaving, setExecSaving] = useState(false);

  // Снимки рабочего стола хостов (превью в списке/профиле).
  const [shotEnabled, setShotEnabled] = useState<boolean>(true);
  const [shotInterval, setShotInterval] = useState<number>(10);
  const [shotQuality, setShotQuality] = useState<number>(72);
  const [shotSaving, setShotSaving] = useState(false);

  const loadDefaultCreds = useCallback(async () => {
    try {
      const data = await apiGetClient("/api/default-creds");
      setDefaultCreds(data || { username: "", has_password: false });
    } catch {
      setDefaultCreds({ username: "", has_password: false });
    }
  }, []);

  const loadExecutionSettings = useCallback(async () => {
    try {
      const data = await fetchExecutionSettings();
      setSshUserMode((data?.config?.ssh_user_mode as SshUserMode) || "service");
      setSshUserField(data?.schema?.ssh_user_mode || null);
      setColdawnRetries(Number(data?.config?.coldawn_retries ?? 3));
      setColdawnField(data?.schema?.coldawn_retries || null);
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }, [showToast]);

  const loadScreenshotSettings = useCallback(async () => {
    try {
      const data = await apiGetClient("/api/admin/screenshot-settings");
      const c = data?.config || {};
      setShotEnabled(Boolean(c.enabled));
      setShotInterval(Number(c.interval_seconds ?? 10));
      setShotQuality(Number(c.jpeg_quality ?? 72));
    } catch {
      /* оставляем дефолты */
    }
  }, []);

  useEffect(() => { loadDefaultCreds(); }, [loadDefaultCreds]);
  useEffect(() => { loadExecutionSettings(); }, [loadExecutionSettings]);
  useEffect(() => { loadScreenshotSettings(); }, [loadScreenshotSettings]);

  async function toggleScreenshots(enabled: boolean) {
    const prev = shotEnabled;
    setShotEnabled(enabled);
    setShotSaving(true);
    try {
      const res = await apiPostClient("/api/admin/screenshot-settings", { enabled });
      setShotEnabled(Boolean(res?.config?.enabled));
      showToast(enabled ? "Снимки рабочего стола включены" : "Снимки рабочего стола выключены");
    } catch (err: any) {
      setShotEnabled(prev);
      showToast(err.message, "error");
    } finally {
      setShotSaving(false);
    }
  }

  async function saveScreenshotParams() {
    setShotSaving(true);
    try {
      const res = await apiPostClient("/api/admin/screenshot-settings", {
        interval_seconds: shotInterval,
        jpeg_quality: shotQuality,
      });
      setShotInterval(Number(res?.config?.interval_seconds ?? shotInterval));
      setShotQuality(Number(res?.config?.jpeg_quality ?? shotQuality));
      showToast("Параметры снимков сохранены");
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setShotSaving(false);
    }
  }

  async function saveDefaultCreds(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const username = String(fd.get("default_username") || "").trim();
    const password = String(fd.get("default_password") || "");
    setCredsSaving(true);
    try {
      const body: Record<string, string> = { username };
      if (password) body.password = password;
      const res = await apiPostClient("/api/default-creds/update", body);
      setDefaultCreds({ username: res?.username ?? username, has_password: res?.has_password ?? false });
      showToast("Стандартные креды сохранены");
      (e.currentTarget as HTMLFormElement).reset();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setCredsSaving(false);
    }
  }

  async function changeSshUserMode(mode: SshUserMode) {
    if (mode === sshUserMode) return;
    const prev = sshUserMode;
    setSshUserMode(mode);
    setExecSaving(true);
    try {
      const res = await saveExecutionSettings({ ssh_user_mode: mode });
      setSshUserMode((res?.config?.ssh_user_mode as SshUserMode) || mode);
      showToast("Пользователь исполнения обновлён");
    } catch (err: any) {
      setSshUserMode(prev);
      showToast(err.message, "error");
    } finally {
      setExecSaving(false);
    }
  }

  async function saveColdawnRetries() {
    setExecSaving(true);
    try {
      const res = await saveExecutionSettings({ coldawn_retries: coldawnRetries });
      setColdawnRetries(Number(res?.config?.coldawn_retries ?? coldawnRetries));
      showToast("Число повторов сохранено");
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setExecSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="panel">
        <h3 className="font-semibold mb-1">Стандартные креды</h3>
        <p className="text-sm text-gray-500 mb-4">
          Используются при добавлении хоста, если поля «Пользователь» и «Пароль» не заполнены. Пароль хранится зашифрованным.
        </p>
        <form onSubmit={saveDefaultCreds} className="grid sm:grid-cols-3 gap-4 items-end max-w-3xl">
          <label className="label">
            Пользователь
            <input className="input" name="default_username" placeholder={defaultCreds.username || "не задан"} autoComplete="off" />
          </label>
          <label className="label">
            Пароль
            <input className="input" name="default_password" type="password" placeholder="•••••" autoComplete="new-password" />
          </label>
          <button className="btn" type="submit" disabled={credsSaving}>
            {credsSaving ? "Сохранение..." : "Сохранить"}
          </button>
        </form>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-1">Исполнение команд</h3>
        <p className="text-sm text-gray-500 mb-4">
          Как NetRunner выполняет команды на целевых машинах. Настройки глобальные — на самих хостах ничего не меняется.
        </p>

        <h4 className="text-sm font-medium mb-1">{sshUserField?.label || "Пользователь исполнения"}</h4>
        <p className="text-sm text-gray-500 mb-3">{sshUserField?.hint || "От чьего имени выполняются команды на целевых машинах."}</p>
        <div className="flex gap-3 flex-wrap">
          {(sshUserField?.choices || [
            { value: "service", label: "Сервисный (netrunner-svc)" },
            { value: "primary", label: "Первичный пользователь хоста" },
          ]).map((choice) => (
            <label
              key={choice.value}
              className={`flex items-center gap-2 text-sm cursor-pointer px-3 py-2 rounded-[10px] border transition-colors ${
                sshUserMode === choice.value
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30"
                  : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
              } ${execSaving ? "opacity-60" : ""}`}
            >
              <input
                type="radio"
                name="sshUserMode"
                className="accent-blue-600"
                checked={sshUserMode === choice.value}
                disabled={execSaving}
                onChange={() => changeSshUserMode(choice.value as SshUserMode)}
              />
              {choice.label}
            </label>
          ))}
        </div>

        <div className="mt-5 pt-4 border-t border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-medium mb-1">{coldawnField?.label || "Повторы запуска (coldawn)"}</h4>
          <p className="text-sm text-gray-500 mb-3">{coldawnField?.hint || "Сколько раз повторить запуск, если сценарий не смог начаться."}</p>
          <div className="flex items-end gap-3">
            <label className="label w-44">
              Повторов
              <input
                type="number"
                className="input"
                min={coldawnField?.min ?? 0}
                max={coldawnField?.max ?? 20}
                value={coldawnRetries}
                disabled={execSaving}
                onChange={(e) => setColdawnRetries(Number(e.target.value))}
              />
            </label>
            <button className="btn" onClick={saveColdawnRetries} disabled={execSaving}>Сохранить</button>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-1">Снимки рабочего стола</h3>
        <p className="text-sm text-gray-500 mb-4">
          Периодические превью экранов хостов для просмотра в списке и профиле машины.
          Выключено — превью не собираются вообще, ни для кого.
        </p>

        <label className="flex items-center gap-3 text-sm cursor-pointer mb-4">
          <input
            type="checkbox"
            className="w-4 h-4 accent-blue-600"
            checked={shotEnabled}
            disabled={shotSaving}
            onChange={(e) => toggleScreenshots(e.target.checked)}
          />
          Собирать снимки рабочего стола
        </label>

        <div className={`flex items-end gap-3 flex-wrap ${shotEnabled ? "" : "opacity-50 pointer-events-none"}`}>
          <label className="label w-44">
            Интервал, с
            <input
              type="number"
              className="input"
              min={3}
              max={300}
              value={shotInterval}
              disabled={shotSaving}
              onChange={(e) => setShotInterval(Number(e.target.value))}
            />
          </label>
          <label className="label w-44">
            Качество JPEG
            <input
              type="number"
              className="input"
              min={10}
              max={95}
              value={shotQuality}
              disabled={shotSaving}
              onChange={(e) => setShotQuality(Number(e.target.value))}
            />
          </label>
          <button className="btn" onClick={saveScreenshotParams} disabled={shotSaving}>Сохранить</button>
        </div>
      </div>
    </div>
  );
}
