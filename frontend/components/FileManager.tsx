"use client";

import { useEffect, useRef, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { useToast } from "@/components/Toast";
import { Upload, Download, Trash2, Loader2, FileIcon, Search } from "lucide-react";

export interface UploadedFile {
  id: number;
  name: string;
  size_bytes: number;
  uploaded_by?: string;
  created_at?: string;
}

interface Props {
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} ГБ`;
}

export function FileManager({ selectedIds, onSelectionChange }: Props) {
  const showToast = useToast();
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;
  const inputRef = useRef<HTMLInputElement | null>(null);

  async function loadFiles() {
    setLoading(true);
    try {
      const data = await apiGetClient("/api/uploads");
      setFiles(data || []);
    } catch (err: any) {
      showToast(err.message, "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadFiles();
  }, []);

  function uploadFiles(fileList: FileList) {
    if (!fileList.length) return;
    const form = new FormData();
    Array.from(fileList).forEach((f) => form.append("files", f));

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/python/api/uploads");
    xhr.withCredentials = true;
    setUploading(true);
    setProgress(0);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      setUploading(false);
      setProgress(0);
      if (inputRef.current) inputRef.current.value = "";
      let payload: any = {};
      try {
        payload = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300 && payload.ok) {
        const added: UploadedFile[] = payload.data || [];
        showToast(`Загружено файлов: ${added.length}`);
        // Автоматически отмечаем только что загруженные файлы.
        onSelectionChange([...new Set([...selectedIds, ...added.map((f) => f.id)])]);
        loadFiles();
      } else {
        showToast(payload.error || `Ошибка загрузки (${xhr.status})`, "error");
      }
    };
    xhr.onerror = () => {
      setUploading(false);
      setProgress(0);
      showToast("Сетевая ошибка при загрузке файла", "error");
    };
    xhr.send(form);
  }

  async function deleteFile(id: number, name: string) {
    if (!confirm(`Удалить файл "${name}" из хранилища?`)) return;
    try {
      await apiPostClient("/api/uploads/delete", { id });
      onSelectionChange(selectedIds.filter((x) => x !== id));
      showToast("Файл удалён");
      loadFiles();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  function downloadFile(id: number) {
    const a = document.createElement("a");
    a.href = `/api/python/api/uploads/${id}/download`;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function toggle(id: number) {
    if (selectedIds.includes(id)) onSelectionChange(selectedIds.filter((x) => x !== id));
    else onSelectionChange([...selectedIds, id]);
  }

  // Поиск + пагинация (444+ файлов рендерить разом нельзя — страница виснет)
  const q = query.trim().toLowerCase();
  const filtered = q ? files.filter((f) => f.name.toLowerCase().includes(q)) : files;
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const from = filtered.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const to = Math.min(safePage * PAGE_SIZE, filtered.length);

  return (
    <div className="pt-2 border-t border-gray-100 space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h4 className="font-semibold">Файлы для рассылки</h4>
          <p className="text-xs text-gray-500">
            Отметьте файлы, которые нужно скопировать на цель. Файлы хранятся на сервере и
            доступны для повторного использования.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files) uploadFiles(e.target.files);
            }}
          />
          <button
            type="button"
            className="btn-secondary"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? `Загрузка… ${progress}%` : "Загрузить файлы"}
          </button>
        </div>
      </div>

      {uploading && (
        <div className="h-2 w-full bg-gray-100 rounded overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all duration-150"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      <div className="flex items-center gap-2">
        <Search size={15} className="text-gray-400 shrink-0" />
        <input
          className="input py-1.5"
          placeholder="Поиск по имени файла…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
        />
        <span className="text-xs text-gray-500 whitespace-nowrap">{filtered.length} файлов</span>
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        {loading ? (
          <div className="p-4 text-sm text-gray-500 flex items-center gap-2">
            <Loader2 size={16} className="animate-spin" /> Загрузка списка…
          </div>
        ) : files.length === 0 ? (
          <div className="p-4 text-sm text-gray-500">
            Файлов пока нет. Нажмите «Загрузить файлы», чтобы добавить.
          </div>
        ) : (
          <>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-gray-500 border-b border-gray-200">
                <th className="w-10 px-3 py-2"></th>
                <th className="px-3 py-2">Имя файла</th>
                <th className="px-3 py-2 w-28">Размер</th>
                <th className="px-3 py-2 w-24 text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {paged.map((f) => (
                <tr key={f.id} className="border-b border-gray-100 last:border-0">
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      className="accent-blue-600"
                      checked={selectedIds.includes(f.id)}
                      onChange={() => toggle(f.id)}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2">
                      <FileIcon size={15} className="text-gray-400 shrink-0" />
                      {f.name}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-500">{formatSize(f.size_bytes)}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1 justify-end">
                      <button
                        type="button"
                        className="btn-secondary p-1.5"
                        title="Скачать"
                        onClick={() => downloadFile(f.id)}
                      >
                        <Download size={15} />
                      </button>
                      <button
                        type="button"
                        className="btn-secondary p-1.5 text-red-600"
                        title="Удалить из хранилища"
                        onClick={() => deleteFile(f.id, f.name)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between gap-3 px-3 py-2 border-t border-gray-200 bg-slate-50 text-xs text-gray-600">
            <span>
              {filtered.length === 0
                ? "Ничего не найдено"
                : `Показано ${from}–${to} из ${filtered.length}`}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="btn-secondary py-1 px-2"
                disabled={safePage <= 1}
                onClick={() => setPage(safePage - 1)}
              >
                Назад
              </button>
              <span className="px-2">{safePage} / {totalPages}</span>
              <button
                type="button"
                className="btn-secondary py-1 px-2"
                disabled={safePage >= totalPages}
                onClick={() => setPage(safePage + 1)}
              >
                Вперёд
              </button>
            </div>
          </div>
          </>
        )}
      </div>

      {selectedIds.length > 0 && (
        <p className="text-xs text-gray-500">Выбрано файлов: {selectedIds.length}</p>
      )}
    </div>
  );
}
