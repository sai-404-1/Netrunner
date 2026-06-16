"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import {
  LayoutDashboard,
  Server,
  Key,
  Boxes,
  Play,
  History,
  ClipboardList,
  CalendarClock,
  FileText,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";

const nav = [
  { href: "/", label: "Обзор", icon: LayoutDashboard },
  { href: "/hosts", label: "Хосты", icon: Server },
  { href: "/keys", label: "Ключи", icon: Key },
  { href: "/modules", label: "Модули", icon: Boxes },
  { href: "/run", label: "Запуск задачи", icon: Play },
  { href: "/history", label: "История", icon: History },
  { href: "/inventory", label: "Инвентаризация", icon: ClipboardList },
  { href: "/scheduled", label: "Планировщик", icon: CalendarClock },
  { href: "/reports", label: "Отчёты", icon: FileText },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col lg:grid lg:grid-cols-[280px_1fr]">
      <aside className="bg-gradient-to-br from-blue-900 via-bg to-[#020617] text-gray-200 lg:sticky lg:top-0 lg:h-screen p-6 flex flex-col gap-7">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">NetRunner</h1>
            <p className="text-xs text-blue-300 mt-1">Веб-консоль управления</p>
          </div>
          <button className="lg:hidden p-2" onClick={() => setMobileOpen(!mobileOpen)}>
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
        <nav className={`flex-col gap-2 ${mobileOpen ? "flex" : "hidden lg:flex"}`}>
          {nav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-[14px] px-4 py-3 text-sm font-medium transition-colors ${
                  active
                    ? "text-white bg-white/15 border border-white/35 shadow"
                    : "text-gray-300 hover:bg-white/10 hover:text-white"
                }`}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto hidden lg:flex flex-col gap-3">
          {user && (
            <div className="text-sm text-gray-300">
              <span className="text-gray-400">Пользователь:</span> {user.username}
            </div>
          )}
          <button onClick={logout} className="btn-secondary w-full justify-start">
            <LogOut size={16} />
            Выйти
          </button>
        </div>
      </aside>
      <main className="p-6 min-w-0">{children}</main>
    </div>
  );
}
