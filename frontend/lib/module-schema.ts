// Разбор schema_json модуля в поля формы. Используется страницей «Запуск задачи»
// и запуском модуля в контексте профиля хоста — формат один, парсер один.

export interface SelectOption {
  value: string;
  label: string;
}

export interface Placeholder {
  name: string;
  label: string;
  default: string;
  type: string;
  options: SelectOption[];
}

export function parsePlaceholders(schema_json?: string | null): Placeholder[] {
  if (!schema_json) return [];
  try {
    const schema = JSON.parse(schema_json);
    return (schema.placeholders || []).map(([name, label, def, type, options]: any) => ({
      name,
      label,
      default: String(def ?? ""),
      type: type || "text",
      options: (options || []).map((o: any) =>
        Array.isArray(o) ? { value: String(o[0]), label: String(o[1]) } : { value: String(o), label: String(o) }
      ),
    }));
  } catch {
    return [];
  }
}

export function defaultArgs(placeholders: Placeholder[]): Record<string, string> {
  const values: Record<string, string> = {};
  for (const p of placeholders) values[p.name] = p.default;
  return values;
}
