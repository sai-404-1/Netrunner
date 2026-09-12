#!/usr/bin/env bash
# Офлайн-пакеты для сценариев Netrunner (установка без сети).
# Качает приложения напрямую с официальных источников в offline-packages/.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
mkdir -p offline-packages
cd offline-packages || exit 1

DL() { # DL <url> <имя-файла>
  local url="$1" name="$2"
  if [ -s "$name" ]; then echo "[skip] $name (уже есть)"; return; fi
  echo "[get]  $name"
  if curl -fsSL --retry 3 --connect-timeout 20 -o "$name" "$url"; then
    echo "[ok]   $name ($(du -h "$name" | cut -f1))"
  else
    echo "[FAIL] $name <- $url"
  fi
}

echo "=== Начинаю скачивание в offline-packages/ ==="

# 1. MySQL Workbench (Ubuntu 24.04 noble)
DL "https://dev.mysql.com/get/Downloads/MySQLGUITools/mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb" "mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb"

# 2. Draw.io
DL "https://github.com/jgraph/drawio-desktop/releases/download/v31.3.2/drawio-amd64-31.3.2.deb" "drawio-amd64-31.3.2.deb"

# 3. DBeaver CE
DL "https://dbeaver.io/files/dbeaver-ce_latest_amd64.deb" "dbeaver-ce_latest_amd64.deb"

# 4. OnlyOffice Desktop Editors
DL "https://github.com/ONLYOFFICE/DesktopEditors/releases/download/v9.4.0/onlyoffice-desktopeditors_amd64.deb" "onlyoffice-desktopeditors_amd64.deb"

# 5. VS Code (stable, из сценария 12)
DL "https://vscode.download.prss.microsoft.com/dbazure/download/stable/110a328ea54b42367b803ec53ee0bf52ef26b419/code_1.134.0-1787078834_amd64.deb" "code_1.134.0-1787078834_amd64.deb"

# 6. Oracle VirtualBox (Ubuntu 24.04 noble)
DL "https://download.virtualbox.org/virtualbox/7.1.6/virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb" "virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb"

# 7. GIMP 3.2.4 (AppImage, официальный)
DL "https://download.gimp.org/gimp/v3.2/linux/GIMP-3.2.4-x86_64.AppImage" "GIMP-3.2.4-x86_64.AppImage"

# 8. PyCharm Community (tar.gz)
DL "https://download.jetbrains.com/python/pycharm-community-2026.1.4.tar.gz" "pycharm-community-2026.1.4.tar.gz"

# 9. SASM (.deb с OBS)
DL "https://download.opensuse.org/repositories/home:/Dman95/xUbuntu_18.04/amd64/sasm_3.10.1_amd64.deb" "sasm_3.10.1_amd64.deb"

echo "=== Готово ==="
echo
echo "Скачано файлов: $(ls -1 | grep -vE '^$' | wc -l | tr -d ' ')"
ls -la
echo
echo "=== ФАЙЛЫ, ТРЕБУЮЩИЕ apt-ЗАВИСИМОСТЕЙ (скачать скриптом на Debian-машине) ==="
echo "- Pinta                 -> sudo apt download pinta (или в репо)
- MySQL Workbench deps     -> apt download libproj25 libmysqlclient21 libmysqlclient24 ...
- VirtualBox deps          -> apt download dkms libvpx9 libqt5opengl5t64 ..."
