import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";

const DEVICE_COOKIE = "netrunner_device";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const apiUrl = process.env.NETRUNNER_API_URL || "http://127.0.0.1:8000";

  // Стабильный идентификатор устройства (для доверенных устройств / 2FA).
  // httpOnly-cookie, живёт год; создаётся при первом входе.
  let deviceId = request.cookies.get(DEVICE_COOKIE)?.value;
  const newDevice = !deviceId;
  if (!deviceId) deviceId = randomUUID();

  const res = await fetch(`${apiUrl}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: body.username || "",
      password: body.password || "",
      device_id: deviceId,
    }),
  });

  const payload = await res.json().catch(() => ({ ok: false, error: "Login failed" }));

  const setDeviceCookie = (response: NextResponse) => {
    if (newDevice) {
      response.cookies.set({
        name: DEVICE_COOKIE,
        value: deviceId!,
        httpOnly: true,
        secure: false,
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 365,
      });
    }
    return response;
  };

  if (!payload.ok) {
    return setDeviceCookie(
      NextResponse.json({ ok: false, error: payload.error || "Login failed" }, { status: 401 })
    );
  }

  // Требуется второй фактор — токен ещё не выдан, cookie сессии не ставим.
  if (payload.mfa_required) {
    return setDeviceCookie(
      NextResponse.json({
        ok: true,
        mfa_required: true,
        challenge_id: payload.challenge_id,
        telegram_hint: payload.telegram_hint,
        expires_in: payload.expires_in,
      })
    );
  }

  if (!payload.token) {
    return setDeviceCookie(
      NextResponse.json({ ok: false, error: payload.error || "Login failed" }, { status: 401 })
    );
  }

  const response = NextResponse.json({ ok: true, user: payload.user });
  response.cookies.set({
    name: "netrunner_token",
    value: payload.token,
    httpOnly: true,
    secure: false,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return setDeviceCookie(response);
}
