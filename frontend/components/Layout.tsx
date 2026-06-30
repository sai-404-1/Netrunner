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
  CalendarClock,
  User,
  Menu,
  X,
  ShieldCheck,
  ListOrdered,
  Loader2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

const nav = [
  { href: "/", label: "Обзор", icon: LayoutDashboard },
  { href: "/hosts", label: "Хосты", icon: Server },
  { href: "/keys", label: "Ключи", icon: Key },
  { href: "/modules", label: "Модули", icon: Boxes },
  { href: "/run", label: "Запуск задачи", icon: Play },
  { href: "/history", label: "История", icon: History },
  { href: "/scheduled", label: "Планировщик", icon: CalendarClock },
  { href: "/scenarios", label: "Сценарии", icon: ListOrdered },
];

const adminNav = [
  { href: "/admin", label: "Администрирование", icon: ShieldCheck },
];

const TEACHER_ALLOWED = new Set(["/", "/hosts"]);

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isTeacher = user?.role === "teacher" && !user?.is_superuser;

  // Спиннер на время перехода между вкладками: включается по клику на пункт меню,
  // гаснет, когда смонтировалась новая страница (pathname поменялся). Закрывает
  // задержку RSC-навигации по локальной сети.
  const [navigating, setNavigating] = useState(false);
  const navTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startNav = (href: string) => {
    if (href !== pathname) setNavigating(true);
  };
  useEffect(() => {
    if (navTimer.current) clearTimeout(navTimer.current);
    navTimer.current = setTimeout(() => setNavigating(false), 220);
    return () => {
      if (navTimer.current) clearTimeout(navTimer.current);
    };
  }, [pathname]);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[280px_1fr]">
      {/* Затемнение под выезжающим меню (мобилка) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 overflow-y-auto transform transition-transform duration-300 ease-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } lg:sticky lg:top-0 lg:h-screen lg:w-auto lg:translate-x-0 lg:z-auto lg:transition-none bg-gradient-to-br from-blue-900 via-bg to-[#020617] text-gray-200 p-6 flex flex-col gap-7`}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">NetRunner</h1>
            <p className="text-xs text-blue-300 mt-1">Веб-консоль управления</p>
          </div>
          <button className="lg:hidden p-2" onClick={() => setMobileOpen(false)} aria-label="Закрыть меню">
            <X size={22} />
          </button>
        </div>
        <nav className="flex flex-col gap-2">
          {nav.map((item) => {
            if (isTeacher && !TEACHER_ALLOWED.has(item.href)) return null;
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => {
                  setMobileOpen(false);
                  startNav(item.href);
                }}
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
          {user?.is_superuser && (
            <div className="mt-2 pt-2 border-t border-white/10 flex flex-col gap-2">
              {adminNav.map((item) => {
                if (item.href === "/admin" && !user?.is_superuser) return null;
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => {
                  setMobileOpen(false);
                  startNav(item.href);
                }}
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
            </div>
          )}
        </nav>
        <div className="mt-auto flex flex-col gap-3">
          {user && (
            <div className="text-sm text-gray-300">
              <span className="text-gray-400">Пользователь:</span> {user.username}
            </div>
          )}
          <Link
            href="/account"
            onClick={() => {
              setMobileOpen(false);
              startNav("/account");
            }}
            className={`flex items-center gap-3 rounded-[14px] px-4 py-3 text-sm font-medium transition-colors ${
              pathname.startsWith("/account")
                ? "text-white bg-white/15 border border-white/35 shadow"
                : "text-gray-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            <User size={18} />
            Профиль
          </Link>
        </div>
      </aside>
      <div className="min-w-0 flex flex-col relative">
        {/* Спиннер перехода между вкладками (только правая область) */}
        {navigating && (
          <div className="pointer-events-none absolute top-3 right-3 z-[60]">
            <span className="inline-flex items-center gap-2 rounded-full bg-blue-600 text-white text-xs font-medium px-2.5 py-1 shadow-lg">
              <Loader2 size={14} className="animate-spin" />
              Загрузка…
            </span>
          </div>
        )}
        {/* Мобильная шапка с бургером */}
        <div className="lg:hidden sticky top-0 z-30 flex items-center gap-3 px-4 py-3 bg-blue-900 text-white">
          <button className="p-1.5" onClick={() => setMobileOpen(true)} aria-label="Открыть меню">
            <Menu size={22} />
          </button>
          <span className="font-bold">NetRunner</span>
        </div>
        <main className="p-6 min-w-0">
          {/* key={pathname} → ремоунт при смене страницы → проигрывается анимация входа.
              Анимируется только правая область, сайдбар не трогаем. */}
          <div key={pathname} className="page-transition">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
