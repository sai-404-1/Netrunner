"use server";

import { cookies } from "next/headers";

const API_URL = process.env.NETRUNNER_API_URL || "http://127.0.0.1:8000";

export async function getToken() {
  return (await cookies()).get("netrunner_token")?.value || null;
}

async function fetchFromBackend(path: string, options: RequestInit = {}) {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  const payload = await res.json().catch(() => ({ ok: false, error: "Invalid response" }));
  if (!payload.ok) {
    throw new Error(payload.error || "API error");
  }
  return payload.data;
}

export async function apiGet(path: string) {
  return fetchFromBackend(path, { method: "GET" });
}

export async function apiPost(path: string, body: unknown) {
  return fetchFromBackend(path, { method: "POST", body: JSON.stringify(body) });
}

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

export async function fetchReportFile(fileName: string) {
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}/reports/${encodeURIComponent(fileName)}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch report");
  return res.text();
}
