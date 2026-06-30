"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import Layout from "@/components/Layout";
import { useAuth } from "@/components/AuthProvider";

const PUBLIC_PATHS = ["/login"];
const TEACHER_PATHS = ["/", "/hosts", "/login"];

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
      if (!allowed) router.replace("/");
    }
  }, [loading, user, pathname, router]);

  if (isPublic) return <>{children}</>;
  if (loading || !user) return null;
  return <Layout>{children}</Layout>;
}
