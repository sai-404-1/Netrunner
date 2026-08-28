#!/usr/bin/env python3
"""Обновляет сценарии: file_ids = app + ТОЛЬКО зависимости своего приложения.
Сопоставление: имена из app_tree.json ↔ deps_file_ids.json (по имени пакета до первого _)."""
import json, os, sqlite3

DB = os.path.join(os.path.dirname(__file__), "data", "netrunner.db")
TREE = "/tmp/app_tree.json"
DEPS = os.path.join(os.path.dirname(__file__), "deps_file_ids.json")

SCEN_APP = {
    7: "mysql-workbench-community",
    9: "drawio",
    15: "dbeaver-ce",
    16: "onlyoffice-desktopeditors",
    17: "code",
    18: "virtualbox-7.1",
}
APP_FILE = {
    7: "mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb",
    9: "drawio-amd64-31.3.2.deb",
    15: "dbeaver-ce_latest_amd64.deb",
    16: "onlyoffice-desktopeditors_amd64.deb",
    17: "code_1.134.0-1787078834_amd64.deb",
    18: "virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb",
}

def main():
    tree = json.load(open(TREE))
    deps_map = json.load(open(DEPS))  # имя файла -> [id]

    # имя пакета (до первого _) -> список id
    pkg_ids: dict[str, list[int]] = {}
    for fname, ids in deps_map.items():
        pkg = fname.split("_")[0]
        pkg_ids.setdefault(pkg, []).extend(ids)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    for sid, app in SCEN_APP.items():
        # app_id — первый id в текущем file_ids шага 1 (там app на первом месте)
        row = cur.execute(
            "SELECT config_json FROM scenario_steps WHERE scenario_id=? AND step_order=1", (sid,)).fetchone()
        cur_ids = json.loads(row[0]).get("file_ids", [])
        app_id = cur_ids[0] if cur_ids else None
        if app_id is None:
            print(f"[пропуск] сценарий {sid}: нет file_ids")
            continue
        names = tree.get(app, [])
        ids = []
        missing = []
        for n in names:
            if n in pkg_ids:
                ids.extend(pkg_ids[n])
            else:
                missing.append(n)
        ids = list(dict.fromkeys(ids))  # уникальные, порядок сохраняем
        final = list(dict.fromkeys([app_id] + ids))
        cur.execute(
            "UPDATE scenario_steps SET config_json=? WHERE scenario_id=? AND step_order=1",
            (json.dumps({"file_ids": final, "dest_path": "/tmp/offline"}, ensure_ascii=False), sid))
        print(f"сценарий {sid} ({app}): файлов {len(final)} (app+{len(ids)} deps)"
              + (f" | пропущено имён: {len(missing)}" if missing else ""))

    conn.commit()
    print("Готово.")

if __name__ == "__main__":
    main()
