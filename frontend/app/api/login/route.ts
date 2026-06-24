import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const apiUrl = process.env.NETRUNNER_API_URL || "http://127.0.0.1:8000";

  const res = await fetch(`${apiUrl}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: body.username || "",
      password: body.password || "",
    }),
  });

  const payload = await res.json().catch(() => ({ ok: false, error: "Login failed" }));
  if (!payload.ok || !payload.token) {
    return NextResponse.json({ ok: false, error: payload.error || "Login failed" }, { status: 401 });
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
