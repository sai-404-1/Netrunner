#!/usr/bin/env python3
"""Загружает файлы из offline-packages/ в Netrunner (локальный backend 127.0.0.1:8000)
через /api/uploads и печатает маппинг имя_файла -> id для FILE_IDS в rewrite_scenarios.py."""
import json, os, sys, glob

import requests

BASE = "http://127.0.0.1:8000"
PKG_DIR = os.path.join(os.path.dirname(__file__), "offline-packages")

# файлы, которые грузим (без зависимостей — те отдельно)
TARGETS = [
    "mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb",
    "drawio-amd64-31.3.2.deb",
    "dbeaver-ce_latest_amd64.deb",
    "onlyoffice-desktopeditors_amd64.deb",
    "code_1.134.0-1787078834_amd64.deb",
    "virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb",
    "GIMP-3.2.4-x86_64.AppImage",
    "sasm_3.10.1_amd64.deb",
    "pycharm-2026.2.1.tar.gz",  # скачан Саем
]

def login():
    r = requests.post(f"{BASE}/api/login", json={"username": "sai", "password": "admin"}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]

def upload(token, path):
    name = os.path.basename(path)
    with open(path, "rb") as fh:
        r = requests.post(
            f"{BASE}/api/uploads", headers={"Authorization": f"Bearer {token}"},
            files={"file": (name, fh)}, timeout=1800)
    r.raise_for_status()
    data = r.json()["data"]
    return data[0]["id"], data[0]["name"]

def main():
    if len(sys.argv) > 1:
        only = set(sys.argv[1:])
    else:
        only = set()
    token = login()
    print("логин OK")
    mapping = {}
    for name in TARGETS:
        if only and name not in only:
            continue
        path = os.path.join(PKG_DIR, name)
        if not os.path.exists(path):
            print(f"[пропуск] {name} — файла нет")
            continue
        fid, fname = upload(token, path)
        print(f"[ok] id={fid} {fname}")
        mapping[name] = [fid]
    print("\n=== FILE_IDS ===")
    print(json.dumps(mapping, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
