"use client";

import { UpdatePanel } from "@/components/UpdatePanel";

export default function UpdatePage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Обновление</h2>
        <p className="text-gray-500">Проверка и применение обновлений кода</p>
      </div>
      <div className="panel">
        <UpdatePanel />
      </div>
    </div>
  );
}
