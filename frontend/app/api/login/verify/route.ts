import { NextRequest, NextResponse } from "next/server";

const DEVICE_COOKIE = "netrunner_device";

/** Второй шаг входа: проверка одноразового кода из Telegram (2FA step-up). */
export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const apiUrl = process.env.NETRUNNER_API_URL || "http://127.0.0.1:8000";
  const deviceId = request.cookies.get(DEVICE_COOKIE)?.value || "";

  const res = await fetch(`${apiUrl}/api/login/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      challenge_id: body.challenge_id || "",
      code: body.code || "",
      trust: !!body.trust,
      device_id: deviceId,
    }),
  });

  const payload = await res.json().catch(() => ({ ok: false, error: "Verification failed" }));
  if (!payload.ok || !payload.token) {
    return NextResponse.json(
      { ok: false, error: payload.error || "Verification failed", attempts_left: payload.attempts_left },
      { status: 400 }
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
  return response;
}
