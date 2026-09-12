#!/usr/bin/env python3
"""Добавляет .deb-зависимости (deps_file_ids.json) в сценарии:
- расширяет file_distribute шаг: file_ids = app + все deps
- меняет установку на dpkg -i *.deb (офлайн, без сети)

Применение: apply_deps.py  (после upload_deps.py и rewrite_scenarios.py)
"""
import json, os, sqlite3

DB = os.path.join(os.path.dirname(__file__), "data", "netrunner.db")
DEPS = os.path.join(os.path.dirname(__file__), "deps_file_ids.json")

# сценарии с .deb-установкой (не GIMP/PyCharm)
DEB_SCENARIOS = {7, 9, 15, 16, 17, 18}

# имя app-файла в каждом сценарии (для исключения из "все deps")
APP_FILE = {
    7: "mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb",
    9: "drawio-amd64-31.3.2.deb",
    15: "dbeaver-ce_latest_amd64.deb",
    16: "onlyoffice-desktopeditors_amd64.deb",
    17: "code_1.134.0-1787078834_amd64.deb",
    18: "virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb",
}

def main():
    if not os.path.exists(DEPS):
        sys_exit = __import__("sys").exit
        sys_exit("нет deps_file_ids.json — сначала upload_deps.py")
    with open(DEPS) as fh:
        deps_map = json.load(fh)  # имя .deb -> [id]
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    for sid in DEB_SCENARIOS:
        steps = cur.execute(
            "SELECT id, module_id, config_json FROM scenario_steps WHERE scenario_id=? ORDER BY step_order",
            (sid,)).fetchall()
        app_name = APP_FILE[sid]
        app_id = None
        dist_step = None
        for step_id, mod_id, cfg_json in steps:
            cfg = json.loads(cfg_json)
            if cfg.get("file_ids") is not None:
                dist_step = (step_id, cfg)
                app_id = cfg["file_ids"][0] if cfg["file_ids"] else None
        if dist_step is None:
            print(f"[skip] сценарий {sid}: нет file_distribute")
            continue
        step_id, cfg = dist_step
        # app уже есть в file_ids (первый) — добавляем deps
        extra = [v[0] for k, v in deps_map.items() if k != app_name]
        new_ids = list(dict.fromkeys(cfg["file_ids"] + extra))
        cfg["file_ids"] = new_ids
        cur.execute("UPDATE scenario_steps SET config_json=? WHERE id=?", (json.dumps(cfg, ensure_ascii=False), step_id))
        # шаг установки -> dpkg -i *.deb
        install_step = [s for s in steps if s[0] != step_id][0]
        new_cmd = "cd /tmp/offline && sudo dpkg -i *.deb 2>/dev/null || sudo apt-get -f install -y 2>/dev/null; dpkg -s $(dpkg-deb -f %s Package 2>/dev/null) >/dev/null 2>&1 && echo OK || echo ПРОВЕРИТЬ" % app_name
        icfg = json.loads(install_step[2])
        icfg["command"] = new_cmd
        cur.execute("UPDATE scenario_steps SET config_json=? WHERE id=?", (json.dumps(icfg, ensure_ascii=False), install_step[0]))
        print(f"[ok] сценарий {sid}: file_ids={len(new_ids)}, установка через dpkg -i *.deb")
    conn.commit()
    print("Готово.")

if __name__ == "__main__":
    main()
