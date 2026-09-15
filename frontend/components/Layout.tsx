"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { TerminalManagerProvider, useTerminalManager, confirmDisconnect } from "@/components/TerminalManagerProvider";
import {
  LayoutDashboard,
  Server,
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
  TerminalSquare,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

const nav = [
  { href: "/", label: "Обзор", icon: LayoutDashboard },
  { href: "/hosts", label: "Хосты", icon: Server },
  { href: "/modules", label: "Модули", icon: Boxes },
  { href: "/history", label: "История", icon: History },
  { href: "/scheduled", label: "Планировщик", icon: CalendarClock },
  { href: "/scenarios", label: "Сценарии", icon: ListOrdered },
];

const adminNav = [
  { href: "/admin", label: "Администрирование", icon: ShieldCheck },
];

// Вкладки, которые по опыту использования оказываются самыми частыми —
// вынесены в отдельную группу над остальными (как Администрирование отделено
// от общего списка). Порядок внутри группы дальше уточняется реальной
// частотой кликов (см. NAV_USAGE_KEY), это только стартовые веса.
// «Запуск задачи» (/run) из сайдбара убран: блок запуска перенесён на «Хосты».
const FREQUENT_HREFS = ["/modules", "/hosts"];
const NAV_USAGE_KEY = "netrunner_nav_usage";
const NAV_USAGE_SEED: Record<string, number> = { "/modules": 2, "/hosts": 1 };

function loadNavUsage(): Record<string, number> {
  try {
    const stored = window.localStorage.getItem(NAV_USAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch {}
  return {};
}

function recordNavClick(href: string) {
  try {
    const merged = { ...NAV_USAGE_SEED, ...loadNavUsage() };
    merged[href] = (merged[href] || 0) + 1;
    window.localStorage.setItem(NAV_USAGE_KEY, JSON.stringify(merged));
  } catch {}
}

const TEACHER_ALLOWED = new Set(["/hosts", "/modules", "/history", "/scheduled", "/scenarios", "/account"]);
const LAST_TAB_KEY = "netrunner_last_tab";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <TerminalManagerProvider>
      <LayoutInner>{children}</LayoutInner>
    </TerminalManagerProvider>
  );
}

function LayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const terminalManager = useTerminalManager();
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

  // Порядок внутри групп уточняется реальной частотой кликов, стартуя с
  // NAV_USAGE_SEED (тот же на сервере и клиенте — без hydration mismatch);
  // фактические счётчики из localStorage подмешиваются одним тиком после
  // монтирования. Состав групп не пересчитывается посреди сессии — только
  // порядок внутри уже сформированных групп, чтобы пункты меню не прыгали.
  const [navUsage, setNavUsage] = useState<Record<string, number>>(NAV_USAGE_SEED);
  useEffect(() => {
    setNavUsage({ ...NAV_USAGE_SEED, ...loadNavUsage() });
  }, []);

  // На чистой загрузке приложения (Layout монтируется один раз на реальный
  // заход в браузер — при переходах между вкладками внутри приложения он не
  // перемонтируется) — если открылись на «/», перекидываем на последнюю
  // активную вкладку. deps=[] гарантирует, что это сработает только при
  // самой загрузке, а не при обычном клике на «Обзор» из сайдбара.
  useEffect(() => {
    if (pathname !== "/") return;
    try {
      const lastTab = window.localStorage.getItem(LAST_TAB_KEY);
      if (lastTab && lastTab !== "/") router.replace(lastTab);
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Запоминаем текущую вкладку при каждом переходе (не /account и не /terminal —
  // они не являются «рабочими» вкладками и не должны быть точкой входа).
  useEffect(() => {
    if (pathname.startsWith("/account") || pathname.startsWith("/terminal")) return;
    try { window.localStorage.setItem(LAST_TAB_KEY, pathname); } catch {}
  }, [pathname]);

  const { overviewItem, frequentNav, restNav } = useMemo(() => {
    const byUsage = (a: { href: string }, b: { href: string }) =>
      (navUsage[b.href] || 0) - (navUsage[a.href] || 0);
    return {
      overviewItem: nav.find((i) => i.href === "/"),
      frequentNav: nav.filter((i) => FREQUENT_HREFS.includes(i.href)).sort(byUsage),
      restNav: nav.filter((i) => !FREQUENT_HREFS.includes(i.href) && i.href !== "/").sort(byUsage),
    };
  }, [navUsage]);

  function renderNavItem(item: { href: string; label: string; icon: typeof LayoutDashboard }) {
    const active = pathname === item.href || pathname.startsWith(item.href + "/");
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={() => {
          setMobileOpen(false);
          startNav(item.href);
          recordNavClick(item.href);
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
  }

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
          {overviewItem && (isTeacher ? TEACHER_ALLOWED.has(overviewItem.href) : true) && (
            <div className="pb-2 border-b border-white/20 flex flex-col gap-2">
              {renderNavItem(overviewItem)}
            </div>
          )}
          {frequentNav.map((item) => {
            if (isTeacher && !TEACHER_ALLOWED.has(item.href)) return null;
            return renderNavItem(item);
          })}
          {restNav.some((item) => !isTeacher || TEACHER_ALLOWED.has(item.href)) && (
            <div className="mt-2 pt-2 border-t border-white/20 flex flex-col gap-2">
              {restNav.map((item) => {
                if (isTeacher && !TEACHER_ALLOWED.has(item.href)) return null;
                return renderNavItem(item);
              })}
            </div>
          )}
          {Boolean(user?.is_superuser) && (
            <div className="mt-2 pt-2 border-t border-white/20 flex flex-col gap-2">
              {adminNav.map((item) => renderNavItem(item))}
            </div>
          )}
        </nav>
        <div className="mt-auto flex flex-col gap-3">
          {/* Подключённые сейчас консоли (WebTerminal) — соединения живут в фоне,
              переживают переключение вкладок (см. TerminalManagerProvider).
              Новые появляются снизу списка, старые визуально "поднимаются" вверх. */}
          {terminalManager.connMetas.length > 0 && (
            <div className="pt-2 border-t border-white/20">
              <div className="text-xs text-blue-300/70 px-1 mb-1.5 flex items-center gap-1.5">
                <TerminalSquare size={12} />
                Машин: {terminalManager.connMetas.length}
              </div>
              <div className="flex flex-col gap-1 max-h-40 overflow-y-auto pr-0.5">
                {terminalManager.connMetas.map((m) => (
                  <div key={m.hostId} className="flex items-center gap-1.5">
                    <Link
                      href={`/terminal?host=${m.hostId}`}
                      onClick={() => {
                        setMobileOpen(false);
                        startNav("/terminal");
                      }}
                      className="flex-1 min-w-0 flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-xs text-gray-300 hover:bg-white/10 hover:text-white transition-colors"
                    >
                      <span className="truncate font-medium flex items-center gap-1.5">
                        <span
                          className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                            m.status === "connected" ? "bg-green-400" : m.status === "connecting" ? "bg-amber-400" : "bg-gray-500"
                          }`}
                        />
                        {m.hostName}
                      </span>
                      <span className="truncate text-gray-400">{m.hostAddress}</span>
                    </Link>
                    <button
                      onClick={() => {
                        if (confirmDisconnect(m.hostName)) terminalManager.disconnect(m.hostId);
                      }}
                      className="shrink-0 w-5 h-5 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors"
                      title="Отключиться"
                    >
                      <X size={11} />
                    </button>
                  </div>
                ))}
              </div>
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
