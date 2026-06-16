import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const token = request.cookies.get("netrunner_token")?.value;
  const apiUrl = process.env.NETRUNNER_API_URL || "http://127.0.0.1:8000";

  if (token) {
    await fetch(`${apiUrl}/api/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.delete("netrunner_token");
  return response;
}
