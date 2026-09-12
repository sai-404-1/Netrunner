#!/usr/bin/env python3
"""Загружает папку .deb-зависимостей в Netrunner пачками (multipart).
Использование: upload_deps.py <папка-с-deb>  → печатает FILE_IDS-маппинг."""
import json, os, sys

import requests

BASE = "http://127.0.0.1:8000"
BATCH = 8  # файлов на один multipart-запрос

def login():
    r = requests.post(f"{BASE}/api/login", json={"username": "sai", "password": "admin"}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "offline-packages/deps-all"
    debs = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".deb"))
    if not debs:
        sys.exit("нет .deb в " + d)
    token = login()
    print(f"файлов: {len(debs)}, батч: {BATCH}")
    mapping = {}
    for i in range(0, len(debs), BATCH):
        chunk = debs[i:i+BATCH]
        files = [("file", (os.path.basename(p), open(p, "rb"))) for p in chunk]
        r = requests.post(f"{BASE}/api/uploads", headers={"Authorization": f"Bearer {token}"}, files=files, timeout=1800)
        try:
            r.raise_for_status()
            data = r.json()["data"]
        except Exception as e:
            print(f"[FAIL] батч {i}: {e} {r.text[:200]}")
            continue
        for row in data:
            print(f"[ok] id={row['id']} {row['name']}")
            mapping[row["name"]] = [row["id"]]
        for _, fh in files:
            fh[1].close()
    out = os.path.join(os.path.dirname(__file__), "deps_file_ids.json")
    with open(out, "w") as fh:
        json.dump(mapping, fh, ensure_ascii=False, indent=1)
    print(f"\nмаппинг сохранён в {out}")

if __name__ == "__main__":
    main()
