#!/usr/bin/env bash
# =============================================================================
# deb-offline-fetch.sh — офлайн-загрузчик зависимостей из .deb
#
# Кидаешь установочный .deb — скрипт сам:
#   1. парсит Depends из пакета (dpkg-deb -f)
#   2. строит ПОЛНОЕ рекурсивное дерево зависимостей (apt-cache depends)
#   3. скачивает все .deb в папку offline-<имя_пакета>/
#
# Запускать на Debian/Ubuntu-машине (той же версии, что целевые хосты),
# с доступом в интернет. Потом папку можно раздать на офлайн-машины
# и установить всё разом:  sudo dpkg -i offline-*/<пакеты>.deb
#
# Использование:  ./deb-offline-fetch.sh <файл.deb> [ещё.deb ...]
# =============================================================================
set -uo pipefail

fetch_one() {
  local deb="$1"
  [ -f "$deb" ] || { echo "[пропуск] нет файла: $deb"; return 1; }

  local pkg out
  pkg=$(dpkg-deb -f "$deb" Package 2>/dev/null)
  [ -n "$pkg" ] || { echo "[ошибка] не удалось прочитать Package из $deb"; return 1; }
  out="offline-${pkg//\//_}"
  mkdir -p "$out"
  echo "=== $deb -> $out/ (пакет: $pkg)"

  # 1) прямые зависимости из control
  local direct
  direct=$(dpkg-deb -f "$deb" Depends 2>/dev/null \
    | tr ',' '\n' \
    | sed -E 's/\([^)]*\)//g' \
    | cut -d'|' -f1 \
    | tr -d ' ' \
    | grep -vE '^$|i386' || true)

  # 2) рекурсивное дерево от прямых зависимостей
  {
    echo "$direct"
    for d in $direct; do
      apt-cache depends --recurse --no-recommends --no-suggests \
        --no-conflicts --no-breaks --no-replaces --no-enhances "$d" 2>/dev/null \
        | grep '^\w' | tr -d ' ' | grep -vE 'i386|:arm'
    done
  } | sort -u | grep -vE '^$' > "$out/list.txt"
  echo "  пакетов в дереве: $(wc -l < "$out/list.txt")"

  # 3) сам .deb приложения кладём рядом
  cp "$deb" "$out/" 2>/dev/null || true

  # 4) качаем всё (параллельно, по 6)
  (cd "$out" && xargs -a list.txt -P 6 -I{} sh -c 'apt-get download {} 2>/dev/null || true')

  local n
  n=$(ls "$out"/*.deb 2>/dev/null | wc -l)
  echo "  ГОТОВО: $n .deb, $(du -sh "$out" | cut -f1)"
  echo "  установка офлайн:  cd $out && sudo dpkg -i *.deb"
}

[ $# -eq 0 ] && { echo "Использование: $0 <файл.deb> [ещё.deb ...]"; exit 1; }

for f in "$@"; do
  fetch_one "$f"
done
echo "=== Все готово ==="
