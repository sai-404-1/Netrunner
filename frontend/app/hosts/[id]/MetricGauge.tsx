"use client";

/** Плитка загрузки как в диспетчере задач: крупный процент, под ним занято/всего
 *  и график последних замеров. История копится на клиенте — сервер отдаёт
 *  мгновенный срез, ряда значений он не хранит. */
export function MetricGauge({
  title,
  subtitle,
  percent,
  detail,
  history,
  accent = "blue",
}: {
  title: string;
  subtitle?: string | null;
  percent: number | null | undefined;
  detail?: string | null;
  history: number[];
  accent?: "blue" | "violet" | "amber" | "emerald";
}) {
  const colors = {
    blue: { stroke: "#3b82f6", fill: "rgba(59,130,246,0.18)", text: "text-blue-600 dark:text-blue-400" },
    violet: { stroke: "#8b5cf6", fill: "rgba(139,92,246,0.18)", text: "text-violet-600 dark:text-violet-400" },
    amber: { stroke: "#f59e0b", fill: "rgba(245,158,11,0.18)", text: "text-amber-600 dark:text-amber-400" },
    emerald: { stroke: "#10b981", fill: "rgba(16,185,129,0.18)", text: "text-emerald-600 dark:text-emerald-400" },
  }[accent];

  const value = percent ?? null;

  return (
    <div className="rounded-[14px] border border-gray-200 dark:border-gray-700 p-4 bg-white/60 dark:bg-gray-800/60">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-gray-600 dark:text-gray-300">{title}</span>
        {subtitle && (
          <span className="text-xs text-gray-500 truncate max-w-[10rem]" title={subtitle}>
            {subtitle}
          </span>
        )}
      </div>
      <div className={`text-4xl font-bold tabular-nums leading-tight ${colors.text}`}>
        {value === null ? "—" : `${value}%`}
      </div>
      <div className="text-xs text-gray-500 h-4">{detail || ""}</div>
      <Sparkline values={history} stroke={colors.stroke} fill={colors.fill} />
    </div>
  );
}

/** Простой график по массиву процентов. Шкала всегда 0–100, чтобы плитки
 *  можно было сравнивать глазами между собой. */
function Sparkline({ values, stroke, fill }: { values: number[]; stroke: string; fill: string }) {
  const width = 200;
  const height = 44;
  const capacity = 30;

  const points = values.slice(-capacity);
  if (points.length < 2) {
    return (
      <div className="h-[44px] flex items-center text-xs text-gray-400">
        накапливаем замеры…
      </div>
    );
  }

  const step = width / (capacity - 1);
  // Ряд прижимаем к правому краю: свежий замер всегда у правой границы.
  const offset = width - (points.length - 1) * step;
  const coords = points.map((v, i) => {
    const x = offset + i * step;
    const y = height - (Math.max(0, Math.min(100, v)) / 100) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[44px] mt-1" preserveAspectRatio="none">
      <polygon
        points={`${offset},${height} ${coords.join(" ")} ${width},${height}`}
        fill={fill}
      />
      <polyline points={coords.join(" ")} fill="none" stroke={stroke} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
