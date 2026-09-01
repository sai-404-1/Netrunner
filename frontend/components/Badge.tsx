export function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    success: "Завершено",
    completed: "Завершено",
    error: "Ошибка",
    failed: "Ошибка",
    // Сценарий прошёл не одинаково на разных хостах: часть машин дошла до конца,
    // часть сошла с дистанции — это не общий провал запуска.
    partial: "Частично",
    skipped: "Пропущено",
    running: "Выполняется",
    pending: "В очереди",
    cancelled: "Отменено",
  };
  const cls =
    status === "success" || status === "completed"
      ? "badge-success"
      : status === "error" || status === "failed"
      ? "badge-error"
      : status === "running"
      ? "badge-running"
      : status === "cancelled" || status === "partial" || status === "skipped"
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
