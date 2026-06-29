#!/bin/bash
# ============================================================
# deploy_update.sh — добавить страницу обновлений в NetRunner
# ============================================================
# Запускать из корня проекта:
#   cd /path/to/netrunner && bash scripts/deploy_update.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."
echo "→ Работаем в $(pwd)"

# ─── 1. Бэкенд: хендлеры + роуты ────────────────────────────
SERVER="webui/server.py"

echo "→ Проверяю, есть ли уже хендлеры обновлений..."
if grep -q "api_update_check" "$SERVER"; then
    echo "  ✓ Хендлеры уже есть, пропускаю."
else
    echo "→ Добавляю хендлеры..."

    # Вставляем три функции перед _periodic_ping
    # Находим строку с объявлением _periodic_ping
    LINE=$(grep -n "async def _periodic_ping" "$SERVER" | head -1 | cut -d: -f1)
    if [ -z "$LINE" ]; then
        echo "  ✗ Не найден _periodic_ping в server.py!"
        exit 1
    fi

    # Читаем файл и вставляем на $LINE (перед _periodic_ping)
    HEAD=$(sed -n "1,$((LINE-1))p" "$SERVER")
    TAIL=$(sed -n "${LINE},\$p" "$SERVER")

    cat > /tmp/_new_server.py << 'PYEOF'
async def api_update_check(request: web.Request) -> web.Response:
    """Проверить наличие обновлений через git."""
    RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.run(["git", "fetch"], cwd=RUNNER_DIR, capture_output=True, text=True, timeout=30)
        result2 = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{u}"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        behind = result2.stdout.strip()
        if behind and behind.isdigit() and int(behind) > 0:
            log = subprocess.run(
                ["git", "--no-pager", "log", "-1", "@{u}", "--pretty=%B"],
                cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
            )
            diff = subprocess.run(
                ["git", "diff", "--stat", "HEAD..@{u}"],
                cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
            )
            return _ok({
                "behind": int(behind),
                "last_message": log.stdout.strip()[:500],
                "diff_stats": diff.stdout.strip()[:2000],
                "has_upstream": True,
            })
        elif behind and behind.isdigit() and int(behind) == 0:
            return _ok({"behind": 0, "has_upstream": True, "message": "Всё актуально"})
        else:
            return _ok({"has_upstream": False, "message": "Нет upstream-ветки. Репа без пулла."})
    except subprocess.TimeoutExpired:
        return _ok({"error": "Таймаут git fetch"})
    except Exception as e:
        return _ok({"error": str(e)[:200]})


async def api_update_diff(request: web.Request) -> web.Response:
    """Показать diff того, что изменится."""
    RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.run(["git", "fetch"], cwd=RUNNER_DIR, capture_output=True, text=True, timeout=30)
        result = subprocess.run(
            ["git", "diff", "HEAD..@{u}", "--stat"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        result2 = subprocess.run(
            ["git", "diff", "HEAD..@{u}", "-p", "--", "*.py", "*.ts", "*.tsx", "*.json", "*.sh", "Dockerfile", "*.yml"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        changed_files = subprocess.run(
            ["git", "diff", "--name-only", "HEAD..@{u}"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=15
        )
        return _ok({
            "stat": result.stdout.strip()[:3000],
            "diff": result2.stdout.strip()[:15000],
            "files": changed_files.stdout.strip()[:2000],
        })
    except Exception as e:
        return _ok({"error": str(e)[:200]})


async def api_update_pull(request: web.Request) -> web.Response:
    """Применить обновления (git pull)."""
    RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=RUNNER_DIR, capture_output=True, text=True, timeout=60
        )
        return _ok({
            "stdout": result.stdout.strip()[:1000],
            "stderr": result.stderr.strip()[:500],
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return _ok({"error": "Таймаут git pull"})
    except Exception as e:
        return _ok({"error": str(e)[:200]})
PYEOF

    echo "$HEAD" > /tmp/_server_part1.py
    cat /tmp/_new_server.py /tmp/_server_part1.py > /tmp/_merged.py
    # На самом деле логика: HEAD + новый_код + TAIL
    echo "$HEAD" > /tmp/_new_server_full.py
    cat /tmp/_new_server.py >> /tmp/_new_server_full.py
    echo "$TAIL" >> /tmp/_new_server_full.py
    cp /tmp/_new_server_full.py "$SERVER"
    echo "  ✓ Хендлеры добавлены"
fi

echo "→ Проверяю роуты..."
if grep -q "/api/update/check" "$SERVER"; then
    echo "  ✓ Роуты уже есть, пропускаю."
else
    # Вставляем строчки роутов перед "# WebSocket"
    LINE=$(grep -n "# WebSocket" "$SERVER" | head -1 | cut -d: -f1)
    if [ -z "$LINE" ]; then
        echo "  ✗ Не найден комментарий # WebSocket!"
        exit 1
    fi
    HEAD=$(sed -n "1,$((LINE-1))p" "$SERVER")
    TAIL=$(sed -n "${LINE},\$p" "$SERVER")

    echo "$HEAD" > "$SERVER"
    echo "" >> "$SERVER"
    echo "    # Update API" >> "$SERVER"
    echo "    app.router.add_get(\"/api/update/check\", api_update_check)" >> "$SERVER"
    echo "    app.router.add_get(\"/api/update/diff\", api_update_diff)" >> "$SERVER"
    echo "    app.router.add_post(\"/api/update/pull\", api_update_pull)" >> "$SERVER"
    echo "" >> "$SERVER"
    echo "$TAIL" >> "$SERVER"
    echo "  ✓ Роуты добавлены"
fi

# ─── 2. Фронтенд: страница /update ──────────────────────────
FRONTEND_PAGE="frontend/app/update/page.tsx"
if [ -f "$FRONTEND_PAGE" ]; then
    echo "  ✓ Страница /update уже существует, пропускаю."
else
    echo "→ Создаю страницу /update..."
    mkdir -p frontend/app/update
    cat > "$FRONTEND_PAGE" << 'FRONTEND'
"use client";

import { useState } from "react";
import { apiGetClient, apiPostClient } from "@/lib/api-client";

export default function UpdatePage() {
  const [status, setStatus] = useState<any>(null);
  const [diff, setDiff] = useState<any>(null);
  const [pullResult, setPullResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);

  async function check() {
    setLoading(true);
    setDiff(null); setPullResult(null);
    try { setStatus(await apiGetClient("/update/check")); }
    catch (e: any) { setStatus({ error: e.message }); }
    setLoading(false);
  }

  async function loadDiff() {
    setShowDiff(!showDiff);
    if (diff || !showDiff) return;
    try { setDiff(await apiGetClient("/update/diff")); }
    catch (e: any) { setDiff({ error: e.message }); }
  }

  async function doPull() {
    setLoading(true); setPullResult(null);
    try {
      const data = await apiPostClient("/update/pull", {});
      setPullResult(data.stdout || data.error || "Готово");
      if (data.returncode === 0) setStatus((s: any) => ({ ...s, behind: 0, message: "Обновлено!" }));
    } catch (e: any) { setPullResult("Ошибка: " + e.message); }
    setLoading(false);
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Обновление</h1>
      <div className="flex gap-4 flex-wrap">
        <button onClick={check} disabled={loading} className="btn-primary">
          {loading ? "⏳ Проверка..." : "Проверить обновления"}
        </button>
        {status?.behind > 0 && (
          <>
            <button onClick={doPull} disabled={loading}
              className="btn-primary bg-green-600 hover:bg-green-700">
              {loading ? "⏳ Загрузка..." : `Применить (${status.behind} коммита)`}
            </button>
            <button onClick={loadDiff} className="btn-secondary">
              {showDiff ? "Скрыть diff" : "Посмотреть изменения"}
            </button>
          </>
        )}
      </div>
      {status && !status.error && (
        <div className="card p-4 space-y-2">
          {status.has_upstream === false &&
            <p className="text-yellow-400">⚠ Нет удалённого репозитория (upstream не настроен)</p>}
          {status.behind === 0 && status.has_upstream &&
            <p className="text-green-400">✅ Актуальная версия</p>}
          {status.behind > 0 && (
            <>
              <p className="text-orange-400">📦 Отставание на <strong>{status.behind}</strong> коммитов</p>
              <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-32 overflow-auto text-gray-300">{status.last_message}</div>
              <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto text-gray-300">{status.diff_stats}</div>
            </>
          )}
        </div>
      )}
      {status?.error && <div className="card p-4 border-red-500 text-red-400">❌ {status.error}</div>}
      {showDiff && diff && (
        <div className="card p-4 space-y-2">
          <h2 className="font-semibold">Изменения файлов</h2>
          {diff.files && <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto">{diff.files}</div>}
          {diff.stat && <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto">{diff.stat}</div>}
          {diff.diff && <details><summary className="cursor-pointer text-sm text-blue-400">Полный diff</summary>
            <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-96 overflow-auto mt-2">{diff.diff}</div></details>}
        </div>
      )}
      {pullResult && (
        <div className="card p-4 space-y-2">
          <h2 className="font-semibold">Результат применения</h2>
          <div className="bg-gray-900 p-3 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-auto">{pullResult}</div>
          <p className="text-sm text-gray-400 mt-2">⚠ Для применения может потребоваться перезапуск контейнера.</p>
        </div>
      )}
    </div>
  );
}
FRONTEND
    echo "  ✓ Страница /update создана"
fi

# ─── 3. Сайдбар: ссылка "Обновление" ───────────────────────
LAYOUT="frontend/components/Layout.tsx"

echo "→ Проверяю сайдбар..."
if grep -q "/update" "$LAYOUT"; then
    echo "  ✓ Ссылка уже есть, пропускаю."
else
    # Добавляем RefreshCw в импорт
    sed -i '' 's/  ListOrdered,/  ListOrdered,\n  RefreshCw,/' "$LAYOUT"
    # Добавляем в adminNav перед закрывающей скобкой
    sed -i '' 's|  { href: "/status", label: "Статус сервера", icon: Activity },|  { href: "/status", label: "Статус сервера", icon: Activity },\n  { href: "/update", label: "Обновление", icon: RefreshCw },|' "$LAYOUT"
    echo "  ✓ Ссылка 'Обновление' добавлена в сайдбар"
fi

# ─── 4. Пересборка Docker ──────────────────────────────────
echo ""
echo "→ Пересобираю Docker..."
docker compose up --build -d 2>&1
echo ""
echo "✓ Готово! NetRunner обновлён и перезапущен."
echo "  Страница: http://localhost:3001/update"
