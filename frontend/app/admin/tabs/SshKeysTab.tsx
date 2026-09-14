"use client";

import { useEffect, useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { BooleanBadge } from "@/components/Badge";
import { DataTable } from "@/components/DataTable";
import { OutputModal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { Eye, Copy, Download } from "lucide-react";

interface SshKey {
  id: number;
  name: string;
  key_type?: string;
  fingerprint?: string;
  public_key?: string;
  created_at?: string;
  is_default?: boolean;
}

export function SshKeysTab() {
  const showToast = useToast();
  const [keys, setKeys] = useState<SshKey[]>([]);
  const [generatedKey, setGeneratedKey] = useState<SshKey | null>(null);
  const [modalText, setModalText] = useState("");
  const [modalTitle, setModalTitle] = useState("");

  async function load() {
    const k = await apiGetClient("/api/ssh-keys");
    setKeys(k || []);
  }

  useEffect(() => { load(); }, []);

  async function generateKey(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      const result = await apiPostClient("/api/keys/generate", {
        key_name: fd.get("key_name"),
        key_type: fd.get("key_type"),
        passphrase: fd.get("passphrase") || null,
      });
      setGeneratedKey(result);
      showToast("Ключ создан");
      (e.currentTarget as HTMLFormElement).reset();
      await load();
    } catch (err: any) {
      showToast(err.message, "error");
    }
  }

  async function copyGenerated() {
    if (!generatedKey?.public_key) return;
    try {
      await navigator.clipboard.writeText(generatedKey.public_key);
      showToast("Скопировано");
    } catch {
      showToast("Не удалось скопировать", "error");
    }
  }

  function downloadGenerated() {
    if (!generatedKey?.public_key) return;
    const blob = new Blob([generatedKey.public_key], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${generatedKey.name}.pub`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Ключ сохранён");
  }

  function viewKeyPublic(key: SshKey) {
    if (!key.public_key) { showToast("Публичный ключ не найден", "error"); return; }
    setModalText(`${key.public_key}\n\nFingerprint: ${key.fingerprint || "—"}\nType: ${key.key_type || "—"}`);
    setModalTitle(`Публичный ключ: ${key.name}`);
  }

  return (
    <div className="space-y-6">
      <div className="panel">
        <h3 className="font-semibold mb-4">Сгенерировать SSH-ключ</h3>
        <form onSubmit={generateKey} className="grid md:grid-cols-4 gap-4 items-end">
          <label className="label">
            Имя ключа
            <input className="input" name="key_name" placeholder="my-key" required />
          </label>
          <label className="label">
            Тип ключа
            <select className="input appearance-none" name="key_type" defaultValue="ed25519">
              <option value="ed25519">Ed25519</option>
              <option value="rsa">RSA</option>
            </select>
          </label>
          <label className="label">
            Пароль ключа (опционально)
            <input className="input" name="passphrase" type="password" placeholder="оставьте пустым, если не нужен" />
          </label>
          <button className="btn" type="submit">Сгенерировать</button>
        </form>

        {generatedKey && (
          <div className="mt-4 p-4 border border-gray-200 dark:border-gray-700 rounded-[14px] bg-white dark:bg-gray-800">
            <p className="text-sm"><strong>Ключ создан:</strong> {generatedKey.name} ({generatedKey.key_type})</p>
            <p className="text-sm mt-1"><strong>Fingerprint:</strong> {generatedKey.fingerprint}</p>
            <label className="label mt-3">
              Публичный ключ
              <textarea className="input font-mono text-sm" rows={4} readOnly value={generatedKey.public_key || ""} />
            </label>
            <div className="flex gap-3 mt-3">
              <button className="btn-secondary flex items-center gap-2" onClick={copyGenerated}>
                <Copy size={16} /> Копировать
              </button>
              <button className="btn-secondary flex items-center gap-2" onClick={downloadGenerated}>
                <Download size={16} /> Сохранить
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-4">Существующие ключи</h3>
        <DataTable
          columns={[
            { title: "Имя", key: "name" },
            { title: "Тип", render: (k) => k.key_type || "—" },
            { title: "Fingerprint", render: (k) => <span className="max-w-xs truncate">{k.fingerprint || "—"}</span> },
            { title: "Создан", render: (k) => formatDate(k.created_at) },
            { title: "По умолчанию", render: (k) => <BooleanBadge value={!!k.is_default} /> },
            {
              title: "",
              render: (k) => (
                <button className="btn-secondary p-2" onClick={() => viewKeyPublic(k)} title="Показать публичный ключ">
                  <Eye size={16} />
                </button>
              ),
            },
          ]}
          rows={keys}
        />
      </div>

      {modalText && <OutputModal text={modalText} title={modalTitle} onClose={() => setModalText("")} />}
    </div>
  );
}
