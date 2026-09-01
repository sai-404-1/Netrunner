#!/usr/bin/env python3
"""Извлекает прямые Depends из .deb приложений (через ar + tarfile) в app_depends.json."""
import io, json, os, re, subprocess, tarfile, gzip, lzma, bz2, zstandard as zstd

PKG = os.path.join(os.path.dirname(__file__), "offline-packages")

APPS = {
    "mysql-workbench-community": "mysql-workbench-community_8.0.44-1ubuntu24.04_amd64.deb",
    "drawio": "drawio-amd64-31.3.2.deb",
    "dbeaver-ce": "dbeaver-ce_latest_amd64.deb",
    "onlyoffice-desktopeditors": "onlyoffice-desktopeditors_amd64.deb",
    "code": "code_1.134.0-1787078834_amd64.deb",
    "virtualbox-7.1": "virtualbox-7.1_7.1.6-167084~Ubuntu~noble_amd64.deb",
}

def ar_extract(deb_path: str, prefix: str) -> bytes:
    """Свой ar-парсер (macOS ar глючит с длинными именами #1/). Возвращает байты члена с заданным префиксом."""
    with open(deb_path, "rb") as fh:
        data = fh.read()
    if data[:8] == b"!<arch>\n":
        data = data[8:]
    pos = 0
    while pos + 60 <= len(data):
        hdr = data[pos:pos + 60]
        name_raw = hdr[0:16].decode("utf-8", "replace").rstrip()
        size_str = hdr[48:58].decode("utf-8", "replace").strip()
        try:
            size = int(size_str)
        except ValueError:
            break
        pos += 60
        real_name = name_raw
        if name_raw.startswith("#1/"):
            name_len = int(name_raw[3:])
            real_name = data[pos:pos + name_len].decode("utf-8", "replace").rstrip()
            pos += name_len
        payload = data[pos:pos + size]
        pos += size
        if pos % 2:
            pos += 1
        if real_name.startswith(prefix):
            return payload
    return b""

def control_text(deb_path):
    blob = ar_extract(deb_path, "control.tar")
    candidates = []
    if blob[:4] == b"\x28\xb5\x2f\xfd":  # zstd
        try: candidates.append(zstd.ZstdDecompressor().decompress(blob))
        except Exception: pass
    for opener in (gzip.decompress, lzma.decompress, bz2.decompress):
        try: candidates.append(opener(blob))
        except Exception: pass
    for raw in candidates:
        try:
            tf = tarfile.open(fileobj=io.BytesIO(raw))
            ctrl_member = next((m for m in tf.getnames() if m.rstrip("/").endswith("control")), None)
            if not ctrl_member:
                continue
            ctrl = tf.extractfile(ctrl_member).read().decode("utf-8", "replace")
            return ctrl
        except Exception:
            continue
    return ""

def parse_depends(ctrl):
    m = re.search(r"^Depends:\s*(.+)$", ctrl, re.M | re.S)
    if not m:
        return []
    # убрать переносы строк с продолжением
    deps = re.sub(r"\n\s+", " ", m.group(1))
    out = []
    for clause in deps.split(","):
        clause = clause.strip()
        if not clause:
            continue
        # альтернативы через | — берём ПЕРВУЮ (достаточно одного варианта)
        name = clause.split("|")[0].strip()
        name = re.sub(r"\([^)]*\)", "", name).strip()
        if name:
            out.append(name)
    return out

result = {}
for app, fname in APPS.items():
    path = os.path.join(PKG, fname)
    ctrl = control_text(path)
    deps = parse_depends(ctrl)
    result[app] = deps
    print(f"{app} ({fname}): {len(deps)} прямых зависимостей")

out = os.path.join(os.path.dirname(__file__), "app_depends.json")
with open(out, "w") as fh:
    json.dump(result, fh, ensure_ascii=False, indent=1)
print(f"\nсохранено в {out}")
