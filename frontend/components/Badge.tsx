export function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    success: "Завершено",
    error: "Ошибка",
    running: "Выполняется",
    pending: "В очереди",
    cancelled: "Отменено",
  };
  const cls =
    status === "success"
      ? "badge-success"
      : status === "error"
      ? "badge-error"
      : status === "running"
      ? "badge-running"
      : status === "cancelled"
      ? "badge-warning"
      : "";
  return <span className={`badge ${cls}`}>{labels[status] || status || "—"}</span>;
}

export function BooleanBadge({ value, yes = "Да", no = "Нет" }: { value: boolean; yes?: string; no?: string }) {
  return <span className={`badge ${value ? "badge-success" : ""}`}>{value ? yes : no}</span>;
}

export function LabelBadge({ text, className = "" }: { text: string; className?: string }) {
  return <span className={`badge ${className}`}>{text}</span>;
}
