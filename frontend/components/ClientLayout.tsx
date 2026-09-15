"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import Layout from "@/components/Layout";
import { useAuth } from "@/components/AuthProvider";

const PUBLIC_PATHS = ["/login"];
// Разделы, доступные преподавателю. Хосты (и профиль машины), модули, история,
// планировщик, сценарии, профиль; плюс терминал и запуск, к которым ведут
// кнопки из профиля хоста и со страницы модулей. Всё остальное («Обзор»,
// «Администрирование», управление ключами) закрыто — редирект на /hosts.
const TEACHER_PATHS = [
  "/hosts",
  "/modules",
  "/history",
  "/scheduled",
  "/scenarios",
  "/account",
  "/terminal",
  "/run",
  "/login",
];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();

  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (!loading && !user && !isPublic) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, isPublic, pathname, router]);

  useEffect(() => {
    if (!loading && user?.role === "teacher" && !user?.is_superuser) {
      const allowed = TEACHER_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
      if (!allowed) router.replace("/hosts");
    }
  }, [loading, user, pathname, router]);

  if (isPublic) return <>{children}</>;
  if (loading || !user) return null;
  return <Layout>{children}</Layout>;
}
