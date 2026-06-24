"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { readFileAsBase64 } from "@/lib/utils";
import { BooleanBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Pencil, Trash2, Play, Plus, X, ChevronDown, ChevronUp } from "lucide-react";
import { useRouter } from "next/navigation";

interface Module {
  id: number;
  name: string;
  slug: string;
  description?: string;
  is_builtin: boolean;
  is_enabled: boolean;
  supports_task_runner?: boolean;
  web_ui_visible?: boolean;
  schema_json?: string;
}

interface SchemaRow {
  id: number;
  name: string;
  label: string;
  default: string;
  type: "text" | "textarea" | "password" | "select" | "radio";
  options: string;
}

let _rowId = 0;
function newRow(): SchemaRow {
  return { id: ++_rowId, name: "", label: "", default: "", type: "text", options: "" };
}

function parseOptions(raw: string) {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const eq = line.indexOf("=");
      return eq > 0 ? [line.slice(0, eq).trim(), line.slice(eq + 1).trim()] : line;
    });
}

function serializeSchema(command: string, rows: SchemaRow[]): string | null {
  const filled = rows.filter((r) => r.name.trim());
  if (!filled.length && !command.trim()) return null;
  const placeholders = filled.map((r) => {
    const entry: any[] = [r.name.trim(), r.label, r.default, r.type];
    if ((r.type === "select" || r.type === "radio") && r.options.trim()) {
      entry.push(parseOptions(r.options));
    }
    return entry;
  });
  const result: any = { placeholders };
  if (command.trim()) result.command = command.trim();
  return JSON.stringify(result);
}

function deserializeSchema(schema_json?: string): { command: string; rows: SchemaRow[] } {
  if (!schema_json) return { command: "", rows: [] };
  try {
    const schema = JSON.parse(schema_json);
    const rows = (schema.placeholders || []).map(([name, label, def, type = "text", options]: any) => ({
      id: ++_rowId,
      name,
      label,
      default: String(def ?? ""),
      type: type || "text",
      options:
        (type === "select" || type === "radio") && options
          ? (options as any[])
              .map((o: any) => (Array.isArray(o) ? `${o[0]}=${o[1]}` : String(o)))
              .join("\n")
          : "",
    }));
    return { command: schema.command || "", rows };
  } catch {
    return { command: "", rows: [] };
  }
}

function countFields(schema_json?: string): number {
  if (!schema_json) return 0;
  try {
    return JSON.parse(schema_json)?.placeholders?.length ?? 0;
  } catch {
    return 0;
  }
}

// ─── Schema Builder ──────────────────────────────────────────────────────────

function SchemaBuilder({
  rows,
  onChange,
}: {
  rows: SchemaRow[];
  onChange: (rows: SchemaRow[]) => void;
}) {
  function update(id: number, patch: Partial<SchemaRow>) {
    onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={row.id} className="grid gap-2 p-3 border border-gray-200 rounded-xl bg-gray-50">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <label className="label text-xs">
              Имя переменной
              <input
                className="input py-1.5 text-sm font-mono"
                placeholder="my_var"
                value={row.name}
                onChange={(e) => update(row.id, { name: e.target.value })}
              />
            </label>
            <label className="label text-xs">
              Подпись
              <input
                className="input py-1.5 text-sm"
                placeholder="Введите значение"
                value={row.label}
                onChange={(e) => update(row.id, { label: e.target.value })}
              />
            </label>
            <label className="label text-xs">
              Значение по умолчанию
              <input
                className="input py-1.5 text-sm"
                value={row.default}
                onChange={(e) => update(row.id, { default: e.target.value })}
              />
            </label>
            <label className="label text-xs">
              Тип поля
              <div className="flex gap-1">
                <select
                  className="input py-1.5 text-sm flex-1"
                  value={row.type}
                  onChange={(e) => update(row.id, { type: e.target.value as SchemaRow["type"] })}
                >
                  <option value="text">Строка</option>
                  <option value="textarea">Многострочный</option>
                  <option value="password">Пароль</option>
                  <option value="radio">Переключатель</option>
                  <option value="select">Список (select)</option>
                </select>
                <button
                  type="button"
                  className="btn-secondary p-1.5 text-red-500 shrink-0"
                  title="Удалить"
                  onClick={() => onChange(rows.filter((r) => r.id !== row.id))}
                >
                  <X size={14} />
                </button>
              </div>
            </label>
          </div>
          {(row.type === "select" || row.type === "radio") && (
            <label className="label text-xs">
              Варианты (по одному на строку: <code className="font-mono">значение</code> или <code className="font-mono">значение=Подпись</code>)
              <textarea
                className="input text-sm font-mono"
                rows={3}
                placeholder={"low=Низкий\nnormal=Обычный\ncritical=Критический"}
                value={row.options}
                onChange={(e) => update(row.id, { options: e.target.value })}
              />
            </label>
          )}
        </div>
      ))}
      <button
        type="button"
        className="btn-secondary text-sm flex items-center gap-1.5 py-1.5"
        onClick={() => onChange([...rows, newRow()])}
      >
        <Plus size={14} /> Добавить поле
      </button>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ModulesPage() {
  const showToast = useToast();
  const router = useRouter();
  const [modules, setModules] = useState<Module[]>([]);
  const [editModule, setEditModule] = useState<Module | null>(null);
  const [moduleFile, setModuleFile] = useState<File | null>(null);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [schemaCommand, setSchemaCommand] = useState("");
  const [schemaRows, setSchemaRows] = useState<SchemaRow[]>([]);
  const [editCommand, setEditCommand] = useState("");
  const [editRows, setEditRows] = useState<SchemaRow[]>([]);

  async function load() {
    const rows = await apiGetClient("/api/modules");
    setModules(rows || []);
  }

  useEffect(() => { load(); }, []);

  function openEdit(m: Module) {
    setEditModule(m);
    const { command, rows } = deserializeSchema(m.schema_json);
    setEditCommand(command);
    setEditRows(rows);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const data: any = {
      name: fd.get("name"),
      slug: fd.get("slug"),
      class_name: "UserModule",
      description: fd.get("description") || null,
      schema_json: serializeSchema(schemaCommand, schemaRows),
    };
    if (moduleFile) {
      data.module_path = `/modules/${moduleFile.name}`;
      data.file_data = await readFileAsBase64(moduleFile);
    }
    try {
      await apiPostClient("/api/modules", data);
      showToast("Модуль добавлен");
      form.reset();
      setModuleFile(null);
      setSchemaCommand("");
      setSchemaRows([]);
      setSchemaOpen(false);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function onUpdate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    try {
      await apiPostClient("/api/modules/update", {
        id: Number(fd.get("id")),
        name: fd.get("name"),
        slug: fd.get("slug"),
        description: fd.get("description") || null,
        is_enabled: fd.get("is_enabled") === "on",
        schema_json: serializeSchema(editCommand, editRows),
      });
      showToast("Модуль обновлён");
      setEditModule(null);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function deleteModule(id: number) {
    if (!confirm(`Удалить модуль #${id}?`)) return;
    try {
      await apiPostClient("/api/modules/delete", { id });
      showToast("Модуль удалён");
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  const visible = modules.filter((m) => m.web_ui_visible !== false);
  const builtin = visible.filter((m) => m.is_builtin);
  const user = visible.filter((m) => !m.is_builtin);

  const columns = (editable: boolean) =>
    [
      { title: "Название", key: "name" },
      { title: "Slug", key: "slug" },
      { title: "Описание", render: (m: Module) => m.description || "—" },
      {
        title: "Поля",
        render: (m: Module) => {
          const n = countFields(m.schema_json);
          return n > 0 ? (
            <span className="badge badge-pending">{n} {n === 1 ? "поле" : n < 5 ? "поля" : "полей"}</span>
          ) : (
            <span className="text-gray-400 text-xs">—</span>
          );
        },
      },
      { title: "Активен", render: (m: Module) => <BooleanBadge value={m.is_enabled} /> },
      {
        title: "",
        render: (m: Module) => (
          <div className="flex gap-2 justify-end">
            {editable && (
              <>
                <button className="btn-secondary p-2" onClick={() => openEdit(m)} title="Редактировать">
                  <Pencil size={16} />
                </button>
                <button
                  className="btn-secondary p-2 text-red-600"
                  onClick={() => deleteModule(m.id)}
                  title="Удалить"
                >
                  <Trash2 size={16} />
                </button>
              </>
            )}
            <button
              className="btn py-1 px-3 text-xs"
              onClick={() => router.push(`/run?module=${m.slug}`)}
              title="Запустить"
            >
              <Play size={14} /> Запуск
            </button>
          </div>
        ),
      },
    ] as any;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Модули</h2>
        <p className="text-gray-500">Доступные для исполнения модули</p>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Добавить модуль</h3>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
            <label className="label">
              Название
              <input className="input" name="name" required />
            </label>
            <label className="label">
              Slug
              <input className="input" name="slug" placeholder="my_module" required />
            </label>
            <label className="label">
              Файл модуля (.py)
              <input
                type="file"
                className="input py-1.5"
                accept=".py"
                onChange={(e) => setModuleFile(e.target.files?.[0] || null)}
              />
            </label>
            <button className="btn" type="submit">
              Добавить
            </button>
          </div>

          <label className="label">
            Описание
            <textarea className="input" name="description" rows={2} />
          </label>

          <div>
            <button
              type="button"
              className="btn-secondary text-sm flex items-center gap-2 py-1.5"
              onClick={() => setSchemaOpen((v) => !v)}
            >
              {schemaOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Схема полей
              {schemaRows.filter((r) => r.name.trim()).length > 0 && (
                <span className="badge badge-pending ml-1">
                  {schemaRows.filter((r) => r.name.trim()).length}
                </span>
              )}
            </button>
            {schemaOpen && (
              <div className="mt-3 space-y-3">
                <label className="label text-sm">
                  SSH-команда
                  <input
                    className="input font-mono text-sm"
                    placeholder="notify-send --urgency=$level $theme $message"
                    value={schemaCommand}
                    onChange={(e) => setSchemaCommand(e.target.value)}
                  />
                </label>
                <p className="text-xs text-gray-400 -mt-1">
                  Хост не указывается — он подставляется ядром автоматически. Переменные записываются как <code className="font-mono">$имя</code>.
                </p>
                <SchemaBuilder rows={schemaRows} onChange={setSchemaRows} />
              </div>
            )}
          </div>
        </form>
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Встроенные модули</h3>
        <DataTable columns={columns(false)} rows={builtin} />
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Пользовательские модули</h3>
        <DataTable columns={columns(true)} rows={user} />
      </div>

      {editModule && (
        <Modal title={`Редактирование — ${editModule.name}`} onClose={() => setEditModule(null)}>
          <form onSubmit={onUpdate} className="space-y-4">
            <input type="hidden" name="id" value={editModule.id} />
            <label className="label">
              Название
              <input className="input" name="name" defaultValue={editModule.name} required />
            </label>
            <label className="label">
              Slug
              <input className="input" name="slug" defaultValue={editModule.slug} required />
            </label>
            <label className="label">
              Описание
              <textarea className="input" name="description" rows={2} defaultValue={editModule.description || ""} />
            </label>
            <label className="label inline-flex flex-row items-center gap-3 cursor-pointer">
              <input type="checkbox" name="is_enabled" defaultChecked={editModule.is_enabled} className="w-5 h-5" />
              <span>Активен</span>
            </label>

            <div className="space-y-3">
              <p className="text-sm font-medium">
                Схема полей
                {editRows.filter((r) => r.name.trim()).length > 0 && (
                  <span className="badge badge-pending ml-2">
                    {editRows.filter((r) => r.name.trim()).length}
                  </span>
                )}
              </p>
              <label className="label text-sm">
                SSH-команда
                <input
                  className="input font-mono text-sm"
                  placeholder="notify-send --urgency=$level $theme $message"
                  value={editCommand}
                  onChange={(e) => setEditCommand(e.target.value)}
                />
              </label>
              <p className="text-xs text-gray-400 -mt-1">
                Хост не указывается — он подставляется ядром. Переменные — <code className="font-mono">$имя</code>.
                Если модуль загружен из файла — команда и схема считаны автоматически.
              </p>
              <SchemaBuilder rows={editRows} onChange={setEditRows} />
            </div>

            <div className="flex gap-3 pt-2">
              <button className="btn" type="submit">
                Сохранить
              </button>
              <button type="button" className="btn-secondary" onClick={() => setEditModule(null)}>
                Отмена
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
