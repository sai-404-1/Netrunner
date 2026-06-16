import { ReactNode } from "react";

export interface Column<T> {
  title: string;
  key?: string;
  render?: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  emptyText = "Нет данных",
}: {
  columns: Column<T>[];
  rows: T[];
  emptyText?: string;
}) {
  return (
    <div className="overflow-auto border border-gray-200 rounded-2xl bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-700">
          <tr>
            {columns.map((col, i) => (
              <th key={i} className="px-4 py-3 text-left font-semibold border-b border-gray-200">
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr key={ri} className="border-b border-gray-100 last:border-b-0 hover:bg-slate-50/50">
                {columns.map((col, ci) => (
                  <td key={ci} className="px-4 py-3 align-middle">
                    {col.render ? col.render(row) : (row as any)[col.key!]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
