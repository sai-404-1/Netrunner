"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useRouter } from "next/navigation";
import { UsersTab } from "./tabs/UsersTab";
import { AgentTab } from "./tabs/AgentTab";
import { DatabaseTab } from "./tabs/DatabaseTab";
import { SshKeysTab } from "./tabs/SshKeysTab";

type AdminTab = "users" | "agent" | "db" | "keys";

const TABS: { id: AdminTab; label: string }[] = [
  { id: "users",  label: "Пользователи" },
  { id: "agent",  label: "Агент" },
  { id: "db",     label: "База данных" },
  { id: "keys",   label: "SSH-ключи" },
];

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<AdminTab>("users");

  useEffect(() => {
    if (user && !user.is_superuser) router.push("/");
  }, [user, router]);

  if (!user?.is_superuser) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Администрирование</h2>
        <p className="text-gray-500">Управление системой, пользователями и доступом</p>
      </div>

      <div className="flex items-center gap-1 border-b border-gray-200 dark:border-gray-700">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className={tab === "users"  ? "" : "hidden"}><UsersTab /></div>
      <div className={tab === "agent"  ? "" : "hidden"}><AgentTab /></div>
      <div className={tab === "db"     ? "" : "hidden"}><DatabaseTab /></div>
      <div className={tab === "keys"   ? "" : "hidden"}><SshKeysTab /></div>
    </div>
  );
}
