import type { NextRequest } from "next/server";

/**
 * Пришёл ли запрос по HTTPS. За обратным прокси (Caddy) Next видит http,
 * поэтому смотрим X-Forwarded-Proto. Клиент на :3001 может подделать заголовок,
 * но так он лишь получит Secure-cookie, которую его же браузер по http не сохранит.
 */
export function isHttpsRequest(request: NextRequest): boolean {
  const proto = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim().toLowerCase();
  return proto === "https" || request.nextUrl.protocol === "https:";
}
