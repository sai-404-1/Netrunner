"use server";

import { cookies } from "next/headers";

export async function getToken() {
  return (await cookies()).get("netrunner_token")?.value || null;
}

export async function setToken(token: string) {
  (await cookies()).set({
    name: "netrunner_token",
    value: token,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
}

export async function deleteToken() {
  (await cookies()).delete("netrunner_token");
}
