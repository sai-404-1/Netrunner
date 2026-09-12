#!/usr/bin/env python3
"""Офлайн-провижининг: качает пакеты, заливает в NetRunner, заводит сценарии.

Зачем: flathub недоступен и постоянно ломается, а ставить всё на каждой машине
из сети — долго и ненадёжно. Скрипт готовит пакеты ОДИН раз на сервере, кладёт
их в хранилище NetRunner, и заводит сценарии «(offline)», которые раздают файлы
по scp и ставят их локально. Сеть на машинах при установке почти не нужна.

Запускать НА СЕРВЕРЕ netrunner:
    python3 scripts/offline_provision.py --all
    python3 scripts/offline_provision.py --download        # только скачать
    python3 scripts/offline_provision.py --upload          # залить + завести сценарии
    python3 scripts/offline_provision.py --all --with-pycharm   # +1.2 ГБ

ВАЖНО про зависимости. Сервер — Ubuntu 20.04 (focal), машины — Mint 22.x
(база Ubuntu 24.04, noble). Зависимости, посчитанные на сервере, ставить на
машины НЕЛЬЗЯ. Поэтому apt-пакеты и их деревья скачиваются внутри контейнера
ubuntu:24.04 (--apt-deps), а вендорские .deb берутся как есть — они самодостаточны.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# Бэкенд слушает 8000 внутри контейнера; снаружи он доступен через прокси
# фронта: /api/python/* переписывается на бэкенд (см. frontend/next.config.js).
BASE_URL = os.environ.get("NETRUNNER_URL", "http://127.0.0.1:3001/api/python")
DOWNLOAD_DIR = Path(os.environ.get("NETRUNNER_OFFLINE_DIR", "offline-packages"))
DEST_ON_HOST = "/tmp/netrunner-offline"
DESKTOP_DIR = "/home/student/Рабочий стол"
DESKTOP_OWNER = "student"

# Целевая база машин. Меняется здесь, если класс переедет на другую версию.
TARGET_CODENAME = "noble"
TARGET_IMAGE = "ubuntu:24.04"


# --- каталог приложений ---------------------------------------------------

def _github_asset(repo: str, pattern: str) -> str:
    """Ссылка на ассет последнего релиза GitHub по подстроке имени."""
    with urllib.request.urlopen(
        f"https://api.github.com/repos/{repo}/releases/latest", timeout=30
    ) as resp:
        data = json.load(resp)
    for asset in data.get("assets", []):
        if pattern in asset["name"]:
            return asset["browser_download_url"]
    raise RuntimeError(f"{repo}: не нашёл ассет с '{pattern}' в релизе {data.get('tag_name')}")


def _jetbrains_tarball(code: str) -> str:
    url = f"https://data.services.jetbrains.com/products/releases?code={code}&latest=true&type=release"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    return data[code][0]["downloads"]["linux"]["link"]


# Каждое приложение: как скачать и какой сценарий из него собрать.
APPS: list[dict] = [
    {
        "key": "drawio",
        "title": "Draw.io",
        "replaces": "#9 (flatpak com.jgraph.drawio.desktop)",
        "kind": "deb",
        "url": lambda: _github_asset("jgraph/drawio-desktop", "amd64"),
        "desktop_file": "drawio.desktop",
    },
    {
        "key": "dbeaver",
        "title": "DBeaver CE",
        "replaces": "#15 (flatpak io.dbeaver.DBeaverCommunity)",
        "kind": "deb",
        "url": lambda: "https://dbeaver.io/files/dbeaver-ce_latest_amd64.deb",
        "desktop_file": "dbeaver-ce.desktop",
    },
    {
        "key": "vscode",
        "title": "VS Code",
        "replaces": "#17 (flatpak com.visualstudio.code), дублирует #12",
        "kind": "deb",
        "url": lambda: "https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64",
        "desktop_file": "code.desktop",
    },
    {
        "key": "onlyoffice",
        "title": "OnlyOffice",
        "replaces": "#16 (flatpak org.onlyoffice.desktopeditors), дублирует #14",
        "kind": "deb",
        "url": lambda: "https://download.onlyoffice.com/install/desktop/editors/linux/onlyoffice-desktopeditors_amd64.deb",
        "desktop_file": "onlyoffice-desktopeditors.desktop",
    },
    {
        "key": "gimp",
        "title": "GIMP",
        "replaces": "#19 (flatpak org.gimp.GIMP)",
        "kind": "apt",          # .deb + дерево зависимостей тянем из noble-контейнера
        "apt_packages": ["gimp"],
        "desktop_file": "gimp.desktop",
    },
    {
        "key": "virtualbox",
        "title": "Oracle VirtualBox",
        "replaces": "#18 (flatpak org.virtualbox.VirtualBox)",
        "kind": "apt",
        "apt_packages": ["virtualbox"],
        "desktop_file": "virtualbox.desktop",
    },
    {
        "key": "pycharm",
        "title": "PyCharm Community",
        "replaces": "#20 (flatpak com.jetbrains.PyCharm-Community)",
        "kind": "tarball",      # .deb у JetBrains не существует, только tar.gz
        "optional": True,       # 1.2 ГБ — включается флагом --with-pycharm
        "url": lambda: _jetbrains_tarball("PCC"),
        "install_dir": "/opt/pycharm",
        "desktop": {
            "Name": "PyCharm Community", "Exec": "/opt/pycharm/bin/pycharm.sh",
            "Icon": "/opt/pycharm/bin/pycharm.png",
            "Categories": "Development;IDE;", "Comment": "Python IDE",
        },
    },
]


# --- скачивание -----------------------------------------------------------

def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def download_direct(app: dict) -> list[Path]:
    """Вендорский пакет — скачивается как есть, зависимостей почти не имеет."""
    target_dir = DOWNLOAD_DIR / app["key"]
    target_dir.mkdir(parents=True, exist_ok=True)
    url = app["url"]()
    # Имя файла берём после всех редиректов — у vscode и dbeaver оно в Location.
    _run(["curl", "-fSL", "--retry", "3", "-OJ", url], cwd=target_dir)
    files = sorted(p for p in target_dir.iterdir() if p.is_file())
    print(f"  {app['title']}: {[f.name for f in files]}")
    return files


def _local_codename() -> str:
    """Кодовое имя базы текущей системы (noble у Mint 22.x)."""
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("UBUNTU_CODENAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def _apt_uris(packages: list[str]) -> list[str]:
    """Ссылки на .deb для пакетов и недостающих зависимостей.

    `--print-uris` ничего не ставит и не требует root: apt лишь считает, что
    ему пришлось бы скачать. Считать это нужно на системе той же базы, что и
    целевые машины, иначе версии будут от чужого релиза.
    """
    out = subprocess.run(
        ["apt-get", "install", "--print-uris", "--reinstall", "-y", *packages],
        capture_output=True, text=True, env={**os.environ, "LANG": "C"},
    ).stdout
    uris = []
    for line in out.splitlines():
        if line.startswith("'http"):
            uris.append(line.split("'")[1])
    return uris


def download_apt(app: dict) -> list[Path]:
    """Пакет из apt вместе с зависимостями.

    Если текущая система той же базы, что целевые машины, считаем зависимости
    нативно. Иначе (например, сервер на focal, а машины на noble) — внутри
    контейнера целевой версии: пакеты от чужого релиза на машины ставить нельзя.
    """
    target_dir = DOWNLOAD_DIR / app["key"]
    target_dir.mkdir(parents=True, exist_ok=True)
    packages = app["apt_packages"]

    if _local_codename() == TARGET_CODENAME:
        uris = _apt_uris(packages)
        if not uris:
            print(f"  {app['title']}: apt не дал ссылок — возможно, всё уже установлено локально")
        for uri in uris:
            _run(["curl", "-fSL", "--retry", "3", "-O", uri], cwd=target_dir)
    else:
        script = (
            "set -e; apt-get update -qq; "
            "apt-get install -y --print-uris --reinstall " + " ".join(packages) + " "
            "| grep -oE \"'[^']+'\" | tr -d \"'\" | grep '^http' > /tmp/uris.txt; "
            "cd /out && wget -q -i /tmp/uris.txt"
        )
        _run([
            "docker", "run", "--rm",
            "-v", f"{target_dir.resolve()}:/out",
            TARGET_IMAGE, "bash", "-lc", script,
        ])

    files = sorted(p for p in target_dir.iterdir() if p.suffix == ".deb")
    print(f"  {app['title']}: {len(files)} .deb (пакет + зависимости)")
    return files


def download_all(with_pycharm: bool) -> dict[str, list[Path]]:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, list[Path]] = {}
    for app in APPS:
        if app.get("optional") and not with_pycharm:
            print(f"[пропуск] {app['title']} — включается флагом --with-pycharm")
            continue
        print(f"[качаю] {app['title']} ({app['replaces']})")
        try:
            if app["kind"] == "apt":
                result[app["key"]] = download_apt(app)
            else:
                result[app["key"]] = download_direct(app)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ОШИБКА] {app['title']}: {exc}")
    return result


# --- заливка в NetRunner и сборка сценариев -------------------------------

def api_login(session, username: str, password: str) -> str:
    """Токен для API.

    Пароль можно не передавать вовсе: если в окружении есть NETRUNNER_TOKEN,
    берём его. Это удобнее и безопаснее — токен видно в куке netrunner_token
    уже открытой сессии, а пароль тогда нигде не всплывает.
    """
    token = os.environ.get("NETRUNNER_TOKEN")
    if token:
        return token.strip()

    resp = session.post(f"{BASE_URL}/api/login",
                        json={"username": username, "password": password}, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        sys.exit(f"вход не удался: {data.get('error') or resp.status_code}")
    if data.get("mfa_required"):
        sys.exit(
            "у этой учётной записи включена двухфакторка через Telegram — "
            "скриптом её не пройти.\nВозьмите токен из куки netrunner_token "
            "уже открытой сессии и запустите с NETRUNNER_TOKEN=<токен>"
        )
    if not data.get("token"):
        sys.exit(f"сервер не вернул токен: {str(data)[:200]}")
    return data["token"]


def upload_files(session, token: str, files: list[Path]) -> list[int]:
    """Загружает пачками — один multipart на 8 файлов, как в upload_deps.py."""
    headers = {"Authorization": f"Bearer {token}"}
    ids: list[int] = []
    for i in range(0, len(files), 8):
        chunk = files[i:i + 8]
        handles = [("file", (p.name, p.open("rb"))) for p in chunk]
        try:
            resp = session.post(f"{BASE_URL}/api/uploads", headers=headers,
                                files=handles, timeout=1800)
            resp.raise_for_status()
            ids.extend(item["id"] for item in resp.json()["data"])
        finally:
            for _, (_, fh) in handles:
                fh.close()
    return ids


def _place_desktop(filename: str) -> str:
    """Хвост команды: положить готовый .desktop на рабочий стол студента."""
    return (
        f'sudo mkdir -p "{DESKTOP_DIR}"; '
        f'sudo cp /tmp/{filename} "{DESKTOP_DIR}/{filename}"; '
        f'sudo chmod +x "{DESKTOP_DIR}/{filename}"; '
        f'sudo chown {DESKTOP_OWNER}:{DESKTOP_OWNER} "{DESKTOP_DIR}/{filename}"'
    )


def desktop_from_package(filename: str) -> str:
    """Ярлык из самого пакета.

    Каждый .deb приносит свой .desktop в /usr/share/applications — там верные
    Exec и Icon, выверенные сопровождающим. Копировать его надёжнее, чем
    сочинять путь к бинарнику: у dbeaver и virtualbox запуск идёт вообще не
    напрямую, а через обёртки.
    """
    return f'cp /usr/share/applications/{filename} /tmp/{filename}; ' + _place_desktop(filename)


def desktop_generated(entry: dict, filename: str) -> str:
    """Ярлык, собранный вручную — для tar.gz, который своего .desktop не несёт."""
    lines = ["[Desktop Entry]", "Encoding=UTF-8", "Type=Application"]
    lines += [f"{key}={value}" for key, value in entry.items()]
    body = "\\n".join(lines) + "\\n"
    return f'printf "{body}" > /tmp/{filename}; ' + _place_desktop(filename)


def build_steps(app: dict, file_ids: list[int], module_ids: dict[str, int]) -> list[dict]:
    """Шаги сценария: раздать файлы -> поставить локально -> ярлык -> убрать за собой."""
    # Свой каталог на приложение: сценарии могут идти подряд, и остатки одного
    # не должны попасть в apt-install другого.
    dest = f"{DEST_ON_HOST}/{app['key']}"

    steps = [{
        "module_id": module_ids["file_distribute"],
        "step_name": f"Раздать пакеты {app['title']}",
        "config": {"dest_path": dest, "file_ids": file_ids},
        "on_failure": "stop",
    }]

    if app["kind"] == "tarball":
        install = (
            f"sudo mkdir -p {app['install_dir']} && "
            f"sudo tar -xzf {dest}/*.tar.gz -C {app['install_dir']} --strip-components=1"
        )
        icon = desktop_generated(app["desktop"], f"{app['key']}.desktop")
    else:
        # apt-get install ./*.deb, а не dpkg -i: apt разложит зависимости из
        # раздатых файлов и не оставит систему в полусломанном состоянии, а
        # чего не хватит — доберёт с зеркала дистрибутива (оно работает,
        # ломается только flathub).
        install = f"sudo apt-get install -y --allow-downgrades {dest}/*.deb"
        icon = desktop_from_package(app["desktop_file"])

    steps.append({
        "module_id": module_ids["mass_ssh"],
        "step_name": f"Установить {app['title']}",
        "config": {"command": install},
        "on_failure": "stop",
    })
    steps.append({
        "module_id": module_ids["mass_ssh"],
        "step_name": "Ярлык на рабочий стол",
        "config": {"command": icon},
        "on_failure": "skip",
    })
    steps.append({
        "module_id": module_ids["mass_ssh"],
        "step_name": "Убрать временные файлы",
        "config": {"command": f"sudo rm -rf {dest}"},
        "on_failure": "skip",
    })
    return steps


def create_scenarios(downloaded: dict[str, list[Path]], username: str, password: str) -> None:
    import requests

    session = requests.Session()
    token = api_login(session, username, password)
    headers = {"Authorization": f"Bearer {token}"}

    resp = session.get(f"{BASE_URL}/api/modules", headers=headers, timeout=30)
    payload = resp.json()
    if not payload.get("ok"):
        sys.exit(f"не удалось получить список модулей: {payload.get('error') or resp.status_code}")
    modules = payload["data"]
    module_ids = {m["slug"]: m["id"] for m in modules}
    for required in ("file_distribute", "mass_ssh"):
        if required not in module_ids:
            sys.exit(f"в системе нет модуля '{required}' — сценарии собрать не из чего")

    for app in APPS:
        files = downloaded.get(app["key"])
        if not files:
            continue
        print(f"[заливаю] {app['title']}: {len(files)} файл(ов)")
        file_ids = upload_files(session, token, files)

        payload = {
            "name": f"{app['title']} (offline)",
            "description": (
                f"Офлайн-установка {app['title']} из заранее скачанных пакетов "
                f"+ ярлык на рабочий стол. Замена {app['replaces']}. "
                f"Сеть на машине не используется."
            ),
            "steps": build_steps(app, file_ids, module_ids),
        }
        resp = session.post(f"{BASE_URL}/api/scenarios", headers=headers,
                            json=payload, timeout=60)
        resp.raise_for_status()
        print(f"  сценарий создан: {payload['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--download", action="store_true", help="только скачать пакеты")
    parser.add_argument("--upload", action="store_true", help="залить и завести сценарии")
    parser.add_argument("--all", action="store_true", help="скачать, залить, завести сценарии")
    parser.add_argument("--with-pycharm", action="store_true", help="включить PyCharm (+1.2 ГБ)")
    parser.add_argument("--user", default=os.environ.get("NETRUNNER_USER", "sai"))
    parser.add_argument("--password", default=os.environ.get("NETRUNNER_PASSWORD", "admin"))
    args = parser.parse_args()

    if not (args.download or args.upload or args.all):
        parser.error("укажите --download, --upload или --all")

    downloaded: dict[str, list[Path]] = {}
    if args.download or args.all:
        downloaded = download_all(args.with_pycharm)

    if args.upload or args.all:
        if not downloaded:
            # Работаем по тому, что уже лежит на диске от прошлого запуска.
            for app in APPS:
                directory = DOWNLOAD_DIR / app["key"]
                if directory.is_dir():
                    files = sorted(p for p in directory.iterdir() if p.is_file())
                    if files:
                        downloaded[app["key"]] = files
        create_scenarios(downloaded, args.user, args.password)


if __name__ == "__main__":
    main()
