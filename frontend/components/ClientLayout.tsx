"use client";

import { usePathname } from "next/navigation";
import Layout from "@/components/Layout";

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";
  if (isLogin) return <>{children}</>;
  return <Layout>{children}</Layout>;
}
