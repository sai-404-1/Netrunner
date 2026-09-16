"""Хелпер, который исполняется НА ХОСТЕ (python3 из stdin) от имени пользователя
графической сессии: список окон приложений с иконками и закрытие окна.

Только стандартная библиотека + ctypes поверх libX11 — на машине ничего не
ставится. Намеренно не зависит от оконного менеджера: список строится обходом
дерева окон, закрытие — ICCCM-сообщением WM_DELETE_WINDOW прямо приложению
(то же, что кнопка «×»: приложение может спросить про несохранённое). Без WM
(упавший Cinnamon, машина без монитора) EWMH-инструменты вроде wmctrl не
работают вовсе, а этот путь работает.

Вывод — одна строка JSON в stdout.
"""

import base64
import ctypes
import ctypes.util
import json
import struct
import sys
import time
import zlib

X = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")

Atom = ctypes.c_ulong
Window = ctypes.c_ulong


class XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("width", ctypes.c_int), ("height", ctypes.c_int),
        ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
        ("visual", ctypes.c_void_p), ("root", Window),
        ("class_", ctypes.c_int), ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong),
        ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
        ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
        ("screen", ctypes.c_void_p),
    ]


class XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
        ("window", Window), ("message_type", Atom), ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


class XEvent(ctypes.Union):
    _fields_ = [("xclient", XClientMessageEvent), ("pad", ctypes.c_long * 24)]


# Окно может исчезнуть между обходом и чтением свойства — дефолтный обработчик
# ошибок Xlib в этом случае завершает процесс. Глушим: ошибка = "нет данных".
_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda d, e: 0)
X.XSetErrorHandler(_ERROR_HANDLER)

X.XOpenDisplay.restype = ctypes.c_void_p
X.XDefaultRootWindow.restype = Window
X.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
X.XInternAtom.restype = Atom
X.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
X.XGetWindowProperty.argtypes = [
    ctypes.c_void_p, Window, Atom, ctypes.c_long, ctypes.c_long, ctypes.c_int, Atom,
    ctypes.POINTER(Atom), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p),
]
X.XQueryTree.argtypes = [
    ctypes.c_void_p, Window, ctypes.POINTER(Window), ctypes.POINTER(Window),
    ctypes.POINTER(ctypes.POINTER(Window)), ctypes.POINTER(ctypes.c_uint),
]
X.XGetWindowAttributes.argtypes = [ctypes.c_void_p, Window, ctypes.POINTER(XWindowAttributes)]
X.XFree.argtypes = [ctypes.c_void_p]
X.XSendEvent.argtypes = [ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_long, ctypes.POINTER(XEvent)]
X.XKillClient.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]

ICON_TARGET = 48
MAX_ICON_SOURCE = 256


def atom(dpy, name):
    return X.XInternAtom(dpy, name.encode(), 0)


def get_prop(dpy, win, prop, req_type=0, long_length=1 << 20):
    """(элементы, формат) свойства; для format=32 Xlib отдаёт массив C long."""
    actual_type, fmt = Atom(), ctypes.c_int()
    nitems, after, data = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
    status = X.XGetWindowProperty(
        dpy, win, prop, 0, long_length, 0, req_type,
        ctypes.byref(actual_type), ctypes.byref(fmt), ctypes.byref(nitems),
        ctypes.byref(after), ctypes.byref(data),
    )
    if status != 0 or not data.value or nitems.value == 0:
        if data.value:
            X.XFree(data)
        return None, 0
    n = nitems.value
    if fmt.value == 8:
        raw = ctypes.string_at(data.value, n)
    elif fmt.value == 16:
        raw = list((ctypes.c_short * n).from_address(data.value))
    else:
        raw = list((ctypes.c_long * n).from_address(data.value))
    X.XFree(data)
    return raw, fmt.value


def children(dpy, win):
    root, parent = Window(), Window()
    kids, count = ctypes.POINTER(Window)(), ctypes.c_uint()
    if not X.XQueryTree(dpy, win, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(kids), ctypes.byref(count)):
        return []
    result = [kids[i] for i in range(count.value)]
    if kids:
        X.XFree(kids)
    return result


def text_prop(dpy, win, name, utf8_atom):
    raw, fmt = get_prop(dpy, win, atom(dpy, name), utf8_atom if name.startswith("_NET") else 0)
    if raw is None or fmt != 8:
        return ""
    return raw.split(b"\0")[0].decode("utf-8", "replace").strip()


def png_from_argb(width, height, pixels):
    """Минимальный PNG (RGBA) без внешних библиотек; большие иконки
    уменьшаются до ICON_TARGET ближайшим соседом."""
    out = ICON_TARGET if max(width, height) > ICON_TARGET else max(width, height)
    rows = bytearray()
    for y in range(out):
        rows.append(0)
        sy = y * height // out
        for x in range(out):
            p = pixels[sy * width + x * width // out] & 0xFFFFFFFF
            rows += bytes(((p >> 16) & 255, (p >> 8) & 255, p & 255, (p >> 24) & 255))

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", out, out, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


def icon_png(dpy, win):
    raw, fmt = get_prop(dpy, win, atom(dpy, "_NET_WM_ICON"), 0)
    if raw is None or fmt != 32:
        return None
    best, i = None, 0
    while i + 2 <= len(raw):
        w, h = raw[i] & 0xFFFFFFFF, raw[i + 1] & 0xFFFFFFFF
        size = w * h
        if w == 0 or h == 0 or i + 2 + size > len(raw):
            break
        if w <= MAX_ICON_SOURCE and h <= MAX_ICON_SOURCE:
            # Ближе всего к целевому размеру, при равенстве — больший.
            score = (abs(w - ICON_TARGET), -w)
            if best is None or score < best[0]:
                best = (score, w, h, i + 2)
        i += 2 + size
    if best is None:
        return None
    _, w, h, start = best
    return base64.b64encode(png_from_argb(w, h, raw[start:start + w * h])).decode()


def app_windows(dpy):
    """Окна приложений: есть WM_CLASS, видимы, не служебные (рабочий стол,
    панели, док, всплывашки), не крошечные. Работает и с перерисовывающим WM
    (клиент вложен во фрейм), и без WM (клиент — прямой потомок корня)."""
    utf8 = atom(dpy, "UTF8_STRING")
    wm_class_atom = atom(dpy, "WM_CLASS")
    type_atom = atom(dpy, "_NET_WM_WINDOW_TYPE")
    allowed_types = {atom(dpy, "_NET_WM_WINDOW_TYPE_NORMAL"), atom(dpy, "_NET_WM_WINDOW_TYPE_DIALOG")}
    pid_atom = atom(dpy, "_NET_WM_PID")
    transient_atom = atom(dpy, "WM_TRANSIENT_FOR")

    found, stack, seen = [], list(children(dpy, X.XDefaultRootWindow(dpy))), set()
    while stack:
        win = stack.pop()
        if win in seen:
            continue
        seen.add(win)
        cls, cfmt = get_prop(dpy, win, wm_class_atom, 0)
        if cls is None or cfmt != 8:
            stack.extend(children(dpy, win))
            continue
        attrs = XWindowAttributes()
        if not X.XGetWindowAttributes(dpy, win, ctypes.byref(attrs)):
            continue
        if attrs.map_state != 2 or attrs.override_redirect or attrs.width < 40 or attrs.height < 40:
            continue
        types, _ = get_prop(dpy, win, type_atom, 0)
        if types and not any(t in allowed_types for t in types):
            continue
        # Диалог, привязанный к окну приложения («Сохранить изменения?»), —
        # часть того приложения, отдельной плиткой он только путает.
        transient, _ = get_prop(dpy, win, transient_atom, 0)
        if transient and transient[0]:
            continue
        parts = [p.decode("utf-8", "replace") for p in cls.split(b"\0") if p]
        title = text_prop(dpy, win, "_NET_WM_NAME", utf8) or text_prop(dpy, win, "WM_NAME", utf8)
        pid, _ = get_prop(dpy, win, pid_atom, 0)
        found.append({
            "id": int(win),
            "title": title,
            "wm_class": parts[-1] if parts else "",
            "wm_instance": parts[0] if parts else "",
            "pid": int(pid[0]) if pid else None,
            "width": attrs.width,
            "height": attrs.height,
            "icon_png": icon_png(dpy, win),
        })
    found.sort(key=lambda w: (w["wm_class"].lower(), w["title"].lower()))
    return found


def exists(dpy, win):
    attrs = XWindowAttributes()
    X.XSync(dpy, 0)
    return bool(X.XGetWindowAttributes(dpy, win, ctypes.byref(attrs)))


def close_window(dpy, win, force):
    # Закрываем только то, что сами же показали бы в списке: произвольный X id
    # (панель, рабочий стол, чужой служебный объект) сюда не пройдёт.
    target = next((w for w in app_windows(dpy) if w["id"] == win), None)
    if target is None:
        return {"ok": False, "error": "Окно не найдено — возможно, уже закрыто"}

    if force:
        X.XKillClient(dpy, win)
        method = "force"
    else:
        protocols, _ = get_prop(dpy, win, atom(dpy, "WM_PROTOCOLS"), 0)
        delete_atom = atom(dpy, "WM_DELETE_WINDOW")
        if not protocols or delete_atom not in protocols:
            return {"ok": False, "error": "Приложение не поддерживает мягкое закрытие — используйте принудительное", "title": target["title"]}
        ev = XEvent()
        ev.xclient.type = 33  # ClientMessage
        ev.xclient.window = win
        ev.xclient.message_type = atom(dpy, "WM_PROTOCOLS")
        ev.xclient.format = 32
        ev.xclient.data[0] = delete_atom
        ev.xclient.data[1] = 0  # CurrentTime
        X.XSendEvent(dpy, win, 0, 0, ctypes.byref(ev))
        method = "graceful"

    deadline = time.time() + 3
    while time.time() < deadline:
        if not exists(dpy, win):
            return {"ok": True, "closed": True, "method": method, "title": target["title"]}
        time.sleep(0.2)
    # Окно осталось: чаще всего приложение спросило «сохранить изменения?».
    return {"ok": True, "closed": False, "method": method, "title": target["title"]}


def main():
    dpy = X.XOpenDisplay(None)
    if not dpy:
        print(json.dumps({"ok": False, "error": "Не удалось подключиться к графической сессии"}, ensure_ascii=False))
        return
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
        if cmd == "list":
            result = {"ok": True, "windows": app_windows(dpy)}
        elif cmd == "close":
            result = close_window(dpy, int(sys.argv[2]), len(sys.argv) > 3 and sys.argv[3] == "force")
        else:
            result = {"ok": False, "error": "Неизвестная команда"}
    finally:
        X.XCloseDisplay(ctypes.c_void_p(dpy))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
