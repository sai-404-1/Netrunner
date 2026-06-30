"use client";

import { ReportsView } from "@/components/ReportsView";

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold">Отчёты</h2>
        <p className="text-gray-500">Формирование и просмотр файлов отчётности</p>
      </div>
      <ReportsView />
    </div>
  );
}
