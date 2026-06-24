export async function apiGetClient(path: string) {
  const res = await fetch(`/api/python${path}`, { credentials: "include" });
  const payload = await res.json().catch(() => ({ ok: false, error: "Invalid response" }));
  if (!payload.ok) throw new Error(payload.error || "API error");
  return payload.data;
}

export async function apiPostClient(path: string, body: unknown) {
  const res = await fetch(`/api/python${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await res.json().catch(() => ({ ok: false, error: "Invalid response" }));
  if (!payload.ok) throw new Error(payload.error || "API error");
  return payload.data;
}

export async function fetchWithAuthClient(path: string, options: RequestInit = {}) {
  const res = await fetch(`/api/python${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  return res;
}

export async function fetchReportFile(fileName: string) {
  const res = await fetch(`/api/python/reports/${encodeURIComponent(fileName)}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch report");
  return res.text();
}
