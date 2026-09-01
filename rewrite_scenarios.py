#!/usr/bin/env python3
"""Переписывает flatpak-сценарии Netrunner на офлайн-установку из файлов
(модуль file_distribute) + полная установка зависимостей + иконка на рабочем
столе пользователя student. Применяется к локальной БД data/netrunner.db.

ВНИМАНИЕ: перед запуском заполни FILE_IDS реальными id из uploaded_files
(после загрузки файлов через /api/uploads). Ключи — имена файлов в offline-packages/.
"""
import sqlite3, os, sys

DB = os.path.join(os.path.dirname(__file__), "data", "netrunner.db")

# id файлов в uploaded_files (локальная БД, после загрузки через upload_offline.py).
FILE_IDS = {
    "mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb": [6],
    "drawio-amd64-31.3.2.deb": [7],
    "dbeaver-ce_latest_amd64.deb": [8],
    "onlyoffice-desktopeditors_amd64.deb": [9],
    "code_1.134.0-1787078834_amd64.deb": [10],
    "virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb": [11],
    "GIMP-3.2.4-x86_64.AppImage": [12],
    "pycharm-2026.2.1.tar.gz": [13],
    # PyCharm — загрузим когда Сай скачает (2026.2.1)
    # SASM — нативного .deb нет, остаётся flatpak
    # Pinta — .deb из Debian pool (загрузить после скачивания)
}

DEST = "/tmp/offline"

# ---------------------------------------------------------------- хелперы

def fids(filename):
    ids = FILE_IDS.get(filename, [0])
    return "[" + ",".join(str(i) for i in ids) + "]"

# Шаг: рассылка файла(ов) на хост через file_distribute.
def step_distribute(*filenames):
    return {
        "module": "file_distribute",
        "config": {"file_ids": [], "dest_path": DEST},
        "files_note": list(filenames),
    }

# Шаг: массовая ssh-команда.
def step_ssh(cmd):
    return {"module": "mass_ssh", "config": {"command": cmd}}

# Шаблон: скопировать установленный .desktop на рабочий стол студента + trusted.
def desktop_from_apps(desktop_file):
    desk = f'"/home/student/Рабочий стол/{desktop_file}"'
    return f"""
sudo cp /usr/share/applications/{desktop_file} {desk}
sudo chmod +x {desk}
sudo chown student:student {desk}
sudo -u student gio set {desk} metadata::trusted true 2>/dev/null || true
echo "Иконка готова: {desktop_file}"
""".strip()

# Установка .deb из /tmp/offline (с зависимостями, которые тоже лежат там).
def install_deb(app_deb, deps_note=""):
    c = f"""
cd {DEST}
sudo apt-get install -y ./{app_deb} 2>/dev/null \\
  || ( sudo dpkg -i {app_deb} 2>/dev/null; sudo apt-get -f install -y 2>/dev/null )
which dpkg >/dev/null && dpkg -s $(dpkg-deb -f {app_deb} Package 2>/dev/null) >/dev/null 2>&1 \\
  && echo "OK: {app_deb} установлен" || echo "ПРОВЕРИТЬ: {app_deb}"
""".strip()
    return c

# ---------------------------------------------------------------- сценарии
# id сценариев из БД: 7=MySQLWB, 8=Pinta, 9=Draw.io, 11=SASM,
# 15=DBeaver, 16=OnlyOffice, 17=VS Code, 18=VirtualBox, 19=GIMP, 20=PyCharm

SCENARIOS = {
    # MySQL Workbench: app.deb + зависимости libproj25/libmysqlclient21 (в offline-packages/deps-mysql-workbench/)
    7: [
        step_distribute("mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb"),
        step_ssh(install_deb("mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb")),
        step_ssh(desktop_from_apps("mysql-workbench.desktop")),
    ],
    # Pinta: .deb из Debian pool (пока не скачан) — добавить после загрузки
    # 8: [
    #     step_distribute("pinta.deb"),
    #     step_ssh("cd %s && sudo apt-get install -y ./pinta.deb 2>/dev/null || sudo dpkg -i pinta.deb" % DEST),
    #     step_ssh(desktop_from_apps("pinta.desktop")),
    # ],
    # Draw.io
    9: [
        step_distribute("drawio-amd64-31.3.2.deb"),
        step_ssh(install_deb("drawio-amd64-31.3.2.deb")),
        step_ssh(desktop_from_apps("drawio.desktop")),
    ],
    # SASM: нативного .deb нет (OBS удалён) — остаётся flatpak, НЕ трогаем
    # 11: [
    #     step_distribute("sasm_3.10.1_amd64.deb"),
    #     step_ssh("cd %s && sudo dpkg -i sasm_3.10.1_amd64.deb 2>/dev/null; sudo apt-get -f install -y 2>/dev/null; echo 'SASM: nasm/gcc/gdb проверьте'" % DEST),
    #     step_ssh(desktop_from_apps("sasm.desktop")),
    # ],
    # DBeaver CE
    15: [
        step_distribute("dbeaver-ce_latest_amd64.deb"),
        step_ssh(install_deb("dbeaver-ce_latest_amd64.deb")),
        step_ssh(desktop_from_apps("dbeaver-ce.desktop")),
    ],
    # OnlyOffice
    16: [
        step_distribute("onlyoffice-desktopeditors_amd64.deb"),
        step_ssh(install_deb("onlyoffice-desktopeditors_amd64.deb")),
        step_ssh(desktop_from_apps("onlyoffice-desktopeditors.desktop")),
    ],
    # VS Code
    17: [
        step_distribute("code_1.134.0-1787078834_amd64.deb"),
        step_ssh(install_deb("code_1.134.0-1787078834_amd64.deb")),
        step_ssh(desktop_from_apps("code.desktop")),
    ],
    # VirtualBox (зависимости dkms и др. — в deps-virtualbox/)
    18: [
        step_distribute("virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb"),
        step_ssh(install_deb("virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb")),
        step_ssh(desktop_from_apps("virtualbox.desktop")),
    ],
    # GIMP — AppImage (офлайн, без установки) + FUSE
    19: [
        step_distribute("GIMP-3.2.4-x86_64.AppImage"),
        step_ssh("sudo apt-get install -y libfuse2 2>/dev/null || sudo apt-get install -y libfuse2t64 2>/dev/null; true"),
        step_ssh("sudo cp /tmp/offline/GIMP-3.2.4-x86_64.AppImage /opt/gimp.AppImage && sudo chmod +x /opt/gimp.AppImage"),
        step_ssh("printf '[Desktop Entry]\\nType=Application\\nName=GIMP\\nExec=/opt/gimp.AppImage\\nIcon=gimp\\nCategories=Graphics;\\nComment=GNU Image Manipulation\\n' | sudo tee /home/student/Рабочий\\ стол/gimp.desktop && sudo chmod +x /home/student/Рабочий\\ стол/gimp.desktop && sudo chown student:student /home/student/Рабочий\\ стол/gimp.desktop && sudo -u student gio set /home/student/Рабочий\\ стол/gimp.desktop metadata::trusted true 2>/dev/null || true"),
    ],
    # PyCharm — tar.gz в /opt
    20: [
        step_distribute("pycharm-2026.2.1.tar.gz"),
        step_ssh("cd /tmp/offline && sudo tar xzf pycharm-2026.2.1.tar.gz -C /opt/ && sudo chown -R root:root /opt/pycharm-2026.2.1"),
        step_ssh("printf '[Desktop Entry]\\nType=Application\\nName=PyCharm Community\\nExec=/opt/pycharm-2026.2.1/bin/pycharm.sh\\nIcon=pycharm\\nCategories=Development;IDE;\\nComment=Python IDE\\n' | sudo tee '/home/student/Рабочий стол/pycharm.desktop' && sudo chmod +x '/home/student/Рабочий стол/pycharm.desktop' && sudo chown student:student '/home/student/Рабочий стол/pycharm.desktop' && sudo -u student gio set '/home/student/Рабочий стол/pycharm.desktop' metadata::trusted true 2>/dev/null || true"),
    ],
}

def main():
    if not os.path.exists(DB):
        sys.exit(f"нет БД: {DB}")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # module id lookup
    mid = {m[0]: m[1] for m in cur.execute("SELECT slug,id FROM modules").fetchall()}
    if "file_distribute" not in mid or "mass_ssh" not in mid:
        sys.exit("нет модулей file_distribute/mass_ssh в БД")
    need = [s for s,steps in SCENARIOS.items() if any(st["module"]=="file_distribute" for st in steps)]
    unresolved = [s for s in need if not any(
        FILE_IDS.get(f) for st in SCENARIOS[s] for f in st.get("files_note",[]))]
    if unresolved:
        print("⚠️ Сценарии БЕЗ file_ids (не применю file_distribute):", unresolved)
        sys.exit("Заполни FILE_IDS (id из uploaded_files) и запусти снова.")

    for sid, steps in SCENARIOS.items():
        # удалить старые шаги
        cur.execute("DELETE FROM scenario_steps WHERE scenario_id=?", (sid,))
        for i, st in enumerate(steps, start=1):
            cfg = dict(st["config"])
            if st["module"] == "file_distribute":
                cfg["file_ids"] = []
                for f in st.get("files_note", []):
                    cfg["file_ids"] += [int(x) for x in (FILE_IDS.get(f) or [])]
            cur.execute(
                "INSERT INTO scenario_steps (scenario_id, module_id, step_order, step_name, config_json, on_failure, retry_count, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (sid, mid[st["module"]], i, st["module"], __import__("json").dumps(cfg, ensure_ascii=False), "stop", 0, __import__("datetime").datetime.utcnow().isoformat()))
        print(f"✅ сценарий {sid}: {len(steps)} шагов")
    conn.commit()
    print("Готово.")

if __name__ == "__main__":
    main()
