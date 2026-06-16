"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api";
import { readFileAsBase64 } from "@/lib/utils";
import { BooleanBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Pencil, Trash2, Play } from "lucide-react";
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
}

export default function ModulesPage() {
  const showToast = useToast();
  const router = useRouter();
  const [modules, setModules] = useState<Module[]>([]);
  const [editModule, setEditModule] = useState<Module | null>(null);
  const [moduleFile, setModuleFile] = useState<File | null>(null);

  async function load() {
    const rows = await apiGetClient("/api/modules");
    setModules(rows || []);
  }

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const data: any = {
      name: fd.get("name"),
      slug: fd.get("slug"),
      class_name: "UserModule",
      description: fd.get("description") || null,
    };
    if (moduleFile) {
      data.module_path = `/modules/${moduleFile.name}`;
      data.file_data = await readFileAsBase64(moduleFile);
    }
    try {
      await apiPostClient("/api/modules", data);
      showToast("Модуль добавлен");
      e.currentTarget.reset();
      setModuleFile(null);
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function onUpdate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await apiPostClient("/api/modules/update", {
        id: Number(fd.get("id")),
        name: fd.get("name"),
        slug: fd.get("slug"),
        description: fd.get("description") || null,
        is_enabled: fd.get("is_enabled") === "on",
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

  const columns = (actions: boolean) =>
    [
      { title: "Название", key: "name" },
      { title: "Slug", key: "slug" },
      { title: "Описание", render: (m: Module) => m.description || "—" },
      { title: "Активен", render: (m: Module) => <BooleanBadge value={m.is_enabled} /> },
      actions
        ? {
            title: "",
            render: (m: Module) => (
              <div className="flex gap-2 justify-end">
                <button className="btn-secondary p-2" onClick={() => setEditModule(m)} title="Редактировать">
                  <Pencil size={16} />
                </button>
                <button className="btn-secondary p-2 text-red-600" onClick={() => deleteModule(m.id)} title="Удалить">
                  <Trash2 size={16} />
                </button>
                <button className="btn py-1 px-3 text-xs" onClick={() => router.push(`/run?module=${m.slug}`)} title="Запустить">
                  <Play size={14} /> Запуск
                </button>
              </div>
            ),
          }
        : {
            title: "",
            render: (m: Module) => (
              <button className="btn py-1 px-3 text-xs" onClick={() => router.push(`/run?module=${m.slug}`)} title="Запустить">
                <Play size={14} /> Запуск
              </button>
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
        <form onSubmit={onSubmit} className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
          <label className="label">
            Название
            <input className="input" name="name" required />
          </label>
          <label className="label">
            Slug
            <input className="input" name="slug" placeholder="my_module" required />
          </label>
          <label className="label">
            Файл модуля
            <input type="file" className="input py-1.5" accept=".py" onChange={(e) => setModuleFile(e.target.files?.[0] || null)} />
          </label>
          <button className="btn" type="submit">
            Добавить
          </button>
          <label className="label md:col-span-2 lg:col-span-4">
            Описание
            <textarea className="input" name="description" rows={3} />
          </label>
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
        <Modal title="Редактирование модуля" onClose={() => setEditModule(null)}>
          <form onSubmit={onUpdate} className="grid gap-4">
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
              <textarea className="input" name="description" rows={3} defaultValue={editModule.description || ""} />
            </label>
            <label className="label inline-flex flex-row items-center gap-3 cursor-pointer">
              <input type="checkbox" name="is_enabled" defaultChecked={editModule.is_enabled} className="w-5 h-5" />
              <span>Активен</span>
            </label>
            <div className="flex gap-3">
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
