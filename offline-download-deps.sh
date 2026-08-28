#!/usr/bin/env bash
# Скачивает .deb пакета + ВСЕ его apt-зависимости в текущую папку (для офлайн-установки).
# Запускать на Debian-машине ТОЙ ЖЕ версии, что целевые хосты (Ubuntu 24.04 noble).
# Использование: ./download_deps.sh <имя-пакета> [ещё-пакет...]
set -uo pipefail

DLD_DEPS() {
  local pkg="$1" out="deps-$pkg"
  mkdir -p "$out"; cd "$out" || return 1
  echo "=== deps for $pkg -> $out/ ==="
  local deps
  deps=$(apt-cache depends --recurse --no-recommends --no-suggests \
         --no-conflicts --no-breaks --no-replaces --no-enhances "$pkg" 2>/dev/null \
         | grep '^\w' | grep -vE '^[a-z-]+:' | tr -d ' ' | sort -u)
  echo "Пакетов в дереве: $(echo "$deps" | grep -c .)"
  # no-download отменяем - качаем реальные .deb
  apt-get download $(echo "$deps" | xargs) 2>/dev/null || true
  cd - >/dev/null
}

for p in "$@"; do
  DLD_DEPS "$p"
done

echo "=== Итог ==="
find . -name '*.deb' -exec du -h {} \; | sort -rh | head -60
echo
echo "Готово. Скопируйте содержимое папок deps-*/ на сервер Netrunner и загрузите через /api/uploads."
