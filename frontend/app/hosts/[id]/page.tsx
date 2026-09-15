"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, Save, TerminalSquare, RefreshCw, Power, RotateCcw, KeyRound,
  Trash2, Clock, HardDrive, ShieldAlert,
} from "lucide-react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/utils";
import { HostScreenshot } from "@/components/HostScreenshot";
import type { HostMetrics, HostProfile } from "@/lib/host-types";
import { MetricGauge } from "./MetricGauge";
import { ConfirmDialog } from "./ConfirmDialog";
import { HostRunPanel } from "./HostRunPanel";

const METRICS_INTERVAL_MS = 5000;
/** Сколько замеров держим для графиков (≈2.5 минуты при шаге 5 с). */
const HISTORY_LIMIT = 30;

type PendingAction =
  | { kind: "reboot" }
  | { kind: "poweroff" }
  | { kind: "delete" }
  | { kind: "leave"; href: string };

interface History {
  cpu: number[];
  ram: number[];
  disk: number[];
  gpu: number[];
}

const EMPTY_HISTORY: History = { cpu: [], ram: [], disk: [], gpu: [] };

function formatUptime(seconds?: number | null): string {
  if (!seconds) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days} д ${hours} ч`;
  if (hours) return `${hours} ч ${minutes} мин`;
  return `${minutes} мин`;
}

function gb(mb: number | null | undefined): string {
  return mb == null ? "—" : `${(mb / 1024).toFixed(1)} ГБ`;
}

export default function HostProfilePage() {
  const params = useParams();
  const router = useRouter();
  const showToast = useToast();
  const hostId = Number(params?.id);

  const [profile, setProfile] = useState<HostProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<HostMetrics | null>(null);
  const [history, setHistory] = useState<History>(EMPTY_HISTORY);

  // Inline-редактирование имени и описания прямо со страницы.
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);

  const host = profile?.host;
  const perms = profile?.permissions;
  const dirty = Boolean(
    host && (name !== host.name || description !== (host.description || "")),
  );

  const load = useCallback(async () => {
    try {
      const data: HostProfile = await apiGetClient(`/api/hosts/${hostId}/profile`);
      setProfile(data);
      setName(data.host.name);
      setDescription(data.host.description || "");
      setLoadError(null);
    } catch (err: any) {
      setLoadError(err.message);
    } finally {
      setLoading(false);
    }
  }, [hostId]);

  useEffect(() => {
    if (Number.isFinite(hostId)) load();
  }, [hostId, load]);

  // --- живые метрики ----------------------------------------------------
  // Один заход по SSH занимает секунды, поэтому следующий замер планируем
  // от завершения предыдущего, а не по общему таймеру: иначе запросы наложатся.
  const inFlight = useRef(false);
  useEffect(() => {
    if (!Number.isFinite(hostId)) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const data: HostMetrics = await apiGetClient(`/api/hosts/${hostId}/metrics`);
        if (stopped) return;
        setMetrics(data);
        if (data.available) {
          setHistory((prev) => {
            const push = (arr: number[], value: number | null | undefined) =>
              value == null ? arr : [...arr, value].slice(-HISTORY_LIMIT);
            return {
              cpu: push(prev.cpu, data.cpu?.percent),
              ram: push(prev.ram, data.ram?.percent),
              disk: push(prev.disk, data.disk?.percent),
              gpu: push(prev.gpu, data.gpu?.percent),
            };
          });
        }
      } catch {
        /* профиль остаётся рабочим и без метрик */
      } finally {
        inFlight.current = false;
        if (!stopped) timer = setTimeout(tick, METRICS_INTERVAL_MS);
      }
    }

    tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [hostId]);

  // --- защита несохранённых правок --------------------------------------
  // Пока правки не подтверждены или не отклонены, страницу не покидаем:
  // beforeunload ловит закрытие вкладки, перехват клика по ссылке — переходы
  // внутри приложения (в App Router нет штатного блокировщика навигации).
  useEffect(() => {
    if (!dirty) return;

    function onBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault();
      e.returnValue = "";
    }

    function onClick(e: MouseEvent) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const anchor = (e.target as HTMLElement | null)?.closest?.("a");
      const href = anchor?.getAttribute("href");
      if (!href || href.startsWith("#") || anchor?.target === "_blank") return;
      if (href === window.location.pathname) return;
      e.preventDefault();
      e.stopPropagation();
      setPending({ kind: "leave", href });
    }

    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [dirty]);

  function navigate(href: string) {
    if (dirty) {
      setPending({ kind: "leave", href });
      return;
    }
    router.push(href);
  }

  // --- действия ---------------------------------------------------------

  async function save() {
    if (!host) return;
    setSaving(true);
    try {
      await apiPostClient("/api/hosts/update", { id: host.id, name, description });
      showToast("Изменения сохранены");
      await load();
      return true;
    } catch (err: any) {
      showToast(err.message, "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function check() {
    setChecking(true);
    try {
      const result = await apiPostClient("/api/hosts/check", { id: hostId });
      showToast(`Хост ${result.host?.name}: ${result.host?.is_active ? "доступен" : "недоступен"}`);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setChecking(false);
    }
  }

  async function power(action: "reboot" | "poweroff") {
    setBusy(true);
    try {
      await apiPostClient(`/api/hosts/${hostId}/power`, { action });
      showToast(action === "reboot" ? "Машина отправлена на перезагрузку" : "Машина выключается");
      setPending(null);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await apiPostClient("/api/hosts/delete", { id: hostId });
      showToast("Хост удалён");
      router.push("/hosts");
    } catch (err: any) {
      showToast(err.message, "error");
      setBusy(false);
    }
  }

  async function reprovision() {
    try {
      const result = await apiPostClient("/api/hosts/reprovision", { id: hostId });
      showToast(`Ключ заново привязан: ${result.is_active ? "хост доступен" : "хост недоступен"}`);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  if (loading) return <p className="text-gray-500">Загрузка профиля…</p>;

  if (loadError || !host || !perms) {
    return (
      <div className="panel flex items-start gap-3">
        <ShieldAlert size={20} className="text-red-500 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">Профиль недоступен</p>
          <p className="text-sm text-gray-500">{loadError || "Хост не найден"}</p>
          <Link href="/hosts" className="btn-secondary mt-3 inline-flex">
            <ArrowLeft size={16} /> К списку хостов
          </Link>
        </div>
      </div>
    );
  }

  const inventory = profile?.inventory;

  return (
    <div className="space-y-6 pb-24">
      {/* Строка 1 — название машины (правится прямо здесь) */}
      <div className="flex items-start gap-3">
        <button className="btn-secondary p-2.5 mt-1" onClick={() => navigate("/hosts")} title="К списку хостов">
          <ArrowLeft size={18} />
        </button>
      </div>

      <div className="grid lg:grid-cols-2 gap-6 items-start">
        {/* Строка 2-3 — действия и описание */}
        <div className="space-y-6">
          <div className="panel space-y-4">
            <div className="flex items-center gap-3">
              <HostScreenshot hostId={host.id} capturedAt={host.screenshot_captured_at} className="w-[240px] h-[135px]" iconSize={40} />
              <div className="min-w-0 flex-1">
                <div className="flex">
                <input
                  className="w-full bg-transparent text-2xl font-bold outline-none border-b-2 border-transparent focus:border-blue-500 transition-colors"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={!perms.edit}
                  title={perms.edit ? "Нажмите, чтобы переименовать" : "Переименование недоступно для вашей роли"}
                />
                <span
                  className={`badge shrink-0 mt-2 ${host.is_active ? "badge-success" : "badge-error"}`}
                >
                  {host.is_active ? "В сети" : "Недоступен"}
                </span>
                </div>
                <p className="text-gray-500 mt-1">
                  {host.username}@{host.address}:{host.port}
                  {host.group_name ? ` · ${host.group_name}` : ""}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {perms.terminal && (
                <button className="btn" onClick={() => navigate(`/terminal?host=${host.id}`)}>
                  <TerminalSquare size={16} /> Открыть терминал
                </button>
              )}
              {perms.power && (
                <>
                  <button
                    className="inline-flex items-center justify-center rounded-[10px] px-3 py-3 text-white bg-amber-500 hover:bg-amber-600 transition-colors"
                    onClick={() => setPending({ kind: "reboot" })}
                    title="Перезагрузить"
                  >
                    <RotateCcw size={16} />
                  </button>
                  <button
                    className="btn-danger justify-center rounded-[10px] px-3 py-3"
                    onClick={() => setPending({ kind: "poweroff" })}
                    title="Выключить"
                  >
                    <Power size={16} />
                  </button>
                </>
              )}
            </div>

            {/* Строка 3 — описание с inline-редактированием */}
            <label className="label">
              Описание
              <textarea
                className="input"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={!perms.edit}
                placeholder={perms.edit ? "Нажмите и пишите — сохранение появится внизу справа" : "—"}
              />
            </label>

            {/* Действия, отфильтрованные по уровню доступа роли */}
            <div className="flex flex-wrap gap-2 pt-3 dark:border-gray-700">
              <button className="btn-secondary" onClick={check} disabled={checking}>
                <RefreshCw size={16} className={checking ? "animate-spin" : ""} /> Пинг
              </button>
              {perms.reprovision && (
                <button className="btn-secondary" onClick={reprovision}>
                  <KeyRound size={16} /> Обновить ключ
                </button>
              )}
              {perms.delete && (
                <button className="btn-danger" onClick={() => setPending({ kind: "delete" })}>
                  <Trash2 size={16} /> Удалить
                </button>
              )}
            </div>
            {!perms.power && !perms.delete && (
              <p className="text-xs text-gray-500">
                Управляющие действия скрыты: ваша роль их не позволяет.
              </p>
            )}
          </div>
        </div>

        {/* Строка 4 — статистика как в диспетчере задач */}
        <div className="panel">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Загрузка</h3>
            <span className="text-xs text-gray-500">
              {metrics?.available
                ? `аптайм ${formatUptime(metrics.uptime_seconds)}`
                : "нет данных"}
            </span>
          </div>

          {metrics && !metrics.available ? (
            <p className="text-sm text-gray-500">
              Машина не отвечает по SSH — показать загрузку не получится.
              {metrics.error ? (
                <span className="block mt-2 font-mono text-xs whitespace-pre-wrap">{metrics.error}</span>
              ) : null}
            </p>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3">
              <MetricGauge
                title="CPU"
                subtitle={metrics?.cpu?.cores ? `${metrics.cpu.cores} ядер` : null}
                percent={metrics?.cpu?.percent}
                detail={metrics?.cpu?.load ? `load ${metrics.cpu.load}` : null}
                history={history.cpu}
                accent="blue"
              />
              <MetricGauge
                title="RAM"
                percent={metrics?.ram?.percent}
                detail={
                  metrics?.ram?.total_mb
                    ? `${gb(metrics.ram.used_mb)} / ${gb(metrics.ram.total_mb)}`
                    : null
                }
                history={history.ram}
                accent="emerald"
              />
              <MetricGauge
                title="Диск /"
                percent={metrics?.disk?.percent}
                detail={
                  metrics?.disk?.total_gb
                    ? `${metrics.disk.used_gb} / ${metrics.disk.total_gb} ГБ`
                    : null
                }
                history={history.disk}
                accent="amber"
              />
              {metrics?.gpu ? (
                <MetricGauge
                  title="GPU"
                  subtitle={metrics.gpu.name}
                  percent={metrics.gpu.percent}
                  detail={
                    metrics.gpu.vram_total_mb
                      ? `VRAM ${gb(metrics.gpu.vram_used_mb)} / ${gb(metrics.gpu.vram_total_mb)}`
                      : null
                  }
                  history={history.gpu}
                  accent="violet"
                />
              ) : (
                <div className="rounded-[14px] border border-dashed border-gray-300 dark:border-gray-700 p-4 flex items-center justify-center text-sm text-gray-400">
                  Видеокарта не обнаружена
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Паспорт машины и запуск модулей — в строку (не колонку) */}
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="panel">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <HardDrive size={16} /> Паспорт машины
              </h3>
              {inventory ? (
                <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <Field label="ОС" value={inventory.os_name} />
                  <Field label="Ядро" value={inventory.kernel} />
                  <Field label="Процессор" value={inventory.cpu_model} />
                  <Field label="Память" value={gb(inventory.ram_mb)} />
                  <Field
                    label="Диски"
                    value={
                      inventory.disks_total_gb != null
                        ? `${inventory.disks_free_gb ?? "?"} / ${inventory.disks_total_gb} ГБ свободно`
                        : null
                    }
                  />
                  <Field label="Пакетов" value={inventory.package_count?.toString()} />
                  <Field label="Снято" value={formatDate(inventory.collected_at)} />
                  <Field label="SSH-ключ" value={host.ssh_key_name} />
                </dl>
              ) : (
                <p className="text-sm text-gray-500">
                  Инвентаризация ещё не собиралась — запустите модуль «Сбор инвентаризации» ниже.
                </p>
              )}
              {host.agent && (
                <p className="text-xs text-gray-500 mt-3 pt-3 border-t dark:border-gray-700">
                  Агент: {host.agent.status}
                  {host.agent.last_seen_at ? ` · был на связи ${formatDate(host.agent.last_seen_at)}` : ""}
                </p>
              )}
            </div>

            {/* Запуск модулей в контексте этой машины — на одном уровне с паспортом */}
            {perms.run_modules && (
              <div className="panel">
                <h3 className="font-semibold mb-3">Запуск на этой машине</h3>
                <HostRunPanel hostId={host.id} modules={profile?.modules || []} />
              </div>
            )}
          </div>

      {/* Логирование системы: таймлайн событий хоста */}
      <div className="panel">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <Clock size={16} /> Журнал машины
        </h3>
        {profile && profile.events.length > 0 ? (
          <ul className="divide-y dark:divide-gray-700 text-sm max-h-80 overflow-auto">
            {profile.events.map((e) => (
              <li key={e.id} className="py-2 flex items-start justify-between gap-3">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 shrink-0">
                  {e.type}
                </span>
                <span className="text-gray-500 text-xs shrink-0">{formatDate(e.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">Событий пока нет.</p>
        )}
      </div>

      {/* Плавающая кнопка сохранения — появляется, как только начали править */}
      {dirty && (
        <button
          className="btn fixed bottom-6 right-6 z-50 shadow-xl"
          onClick={save}
          disabled={saving}
        >
          <Save size={16} /> {saving ? "Сохраняем…" : "Сохранить"}
        </button>
      )}

      {pending?.kind === "leave" && (
        <ConfirmDialog
          title="Есть несохранённые изменения"
          confirmLabel="Сохранить и уйти"
          busy={saving}
          onCancel={() => setPending(null)}
          onConfirm={async () => {
            const href = pending.href;
            if (await save()) router.push(href);
            setPending(null);
          }}
          extraAction={{
            label: "Уйти без сохранения",
            onClick: () => {
              const href = pending.href;
              setName(host.name);
              setDescription(host.description || "");
              setPending(null);
              router.push(href);
            },
          }}
        >
          Имя и описание машины изменены, но не сохранены.
        </ConfirmDialog>
      )}

      {pending?.kind === "reboot" && (
        <ConfirmDialog
          title="Перезагрузить машину?"
          confirmLabel="Перезагрузить"
          busy={busy}
          onCancel={() => setPending(null)}
          onConfirm={() => power("reboot")}
        >
          «{host.name}» уйдёт в перезагрузку. Работа пользователя за этим компьютером прервётся.
        </ConfirmDialog>
      )}

      {pending?.kind === "poweroff" && (
        <ConfirmDialog
          title="Выключить машину?"
          confirmLabel="Выключить"
          danger
          busy={busy}
          onCancel={() => setPending(null)}
          onConfirm={() => power("poweroff")}
        >
          «{host.name}» будет выключена. Включить её удалённо NetRunner не сможет.
        </ConfirmDialog>
      )}

      {pending?.kind === "delete" && (
        <ConfirmDialog
          title="Удалить хост?"
          confirmLabel="Удалить"
          danger
          busy={busy}
          onCancel={() => setPending(null)}
          onConfirm={remove}
        >
          Машина «{host.name}» и её история будут удалены из NetRunner. Сам компьютер не пострадает.
        </ConfirmDialog>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium break-words">{value || "—"}</dd>
    </div>
  );
}
