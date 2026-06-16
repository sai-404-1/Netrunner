from __future__ import annotations

import shutil
import sys
import termios
import tty

from .termdraw import clear_screen, hide_cursor, show_cursor


APP_NAME = "NetRunner"
APP_SUBTITLE = "Система централизованного управления удалёнными хостами"


def read_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch1 = sys.stdin.read(1)

        if ch1 == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                mapping = {
                    "A": "UP",
                    "B": "DOWN",
                    "C": "RIGHT",
                    "D": "LEFT",
                }
                return mapping.get(ch3, f"ESC[{ch3}")
            return "ESC"

        if ch1 == "\x03":
            raise KeyboardInterrupt

        if ch1 in ("\r", "\n"):
            return "ENTER"

        if ch1 in ("\x7f", "\b"):
            return "BACKSPACE"

        if ch1 == "\t":
            return "TAB"

        if ch1 == " ":
            return "SPACE"

        return ch1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def wait_enter():
    input("\nНажмите Enter, чтобы вернуться в меню...")


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(value, max_value))


def fit(text: object, width: int) -> str:
    value = "" if text is None else str(text)
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def centered(text: str, width: int) -> str:
    if len(text) >= width:
        return text[:width]
    return text.center(width)


def get_screen_width() -> int:
    term_size = shutil.get_terminal_size((100, 30))
    return min(max(90, term_size.columns - 2), 120)


def visible_window(menu_items: list[dict], selected_idx: int, available_rows: int):
    visible_count = max(5, available_rows)
    start = 0

    if selected_idx >= visible_count:
        start = selected_idx - visible_count + 1

    end = min(len(menu_items), start + visible_count)
    return start, end


def build_menu_lines(menu_items: list[dict], selected_idx: int) -> list[str]:
    term_size = shutil.get_terminal_size((100, 30))
    width = get_screen_width()
    menu_rows = term_size.lines - 12
    start, end = visible_window(menu_items, selected_idx, menu_rows)

    border = "=" * width
    thin = "-" * width
    item_width = width - 6

    lines: list[str] = [
        border,
        centered(APP_NAME, width),
        centered(APP_SUBTITLE, width),
        border,
        centered("Главное меню", width),
        thin,
    ]

    for idx in range(start, end):
        item = menu_items[idx]
        marker = ">" if idx == selected_idx else " "
        title = fit(item.get("title", "Без названия"), item_width)
        lines.append(f" {marker} {title}")

    lines.extend([
        thin,
        " ↑/↓ — выбор    Enter — открыть    Esc — выход",
    ])

    if len(menu_items) > end - start:
        lines.append(f" Пункты {start + 1}-{end} из {len(menu_items)}")

    lines.append(border)
    return lines


def render(menu_items: list[dict], selected_idx: int):
    clear_screen()
    print("\n".join(build_menu_lines(menu_items, selected_idx)), flush=True)


# функция проверки вызова

def exec(number: int):
    print(number)


def main(map_of_functions=None):
    if map_of_functions is None:
        menu_items = [
            {"title": "Тестовый пункт 1", "exec": exec},
            {"title": "Тестовый пункт 2", "exec": exec},
            {"title": "Тестовый пункт 3", "exec": exec},
        ]
    else:
        menu_items = map_of_functions

    if not menu_items:
        print("Нет доступных действий.")
        return

    selected_idx = 0

    try:
        hide_cursor()
        render(menu_items, selected_idx)

        while True:
            key = read_key()

            if key == "UP":
                selected_idx -= 1
            elif key == "DOWN":
                selected_idx += 1

            selected_idx = clamp(selected_idx, 0, len(menu_items) - 1)

            if key == "ENTER":
                action = menu_items[selected_idx]["exec"]
                title = menu_items[selected_idx].get("title", "Действие")

                clear_screen()
                width = get_screen_width()
                print("=" * width)
                print(centered(APP_NAME, width))
                print(centered(title, width))
                print("=" * width)

                if hasattr(action, "exec"):
                    action.exec()
                else:
                    action(selected_idx)

                wait_enter()
                render(menu_items, selected_idx)
                continue

            if key == "ESC":
                clear_screen()
                print("Выход из NetRunner.\n")
                break

            render(menu_items, selected_idx)

    except KeyboardInterrupt:
        clear_screen()
        print("Выход по Ctrl+C.\n")
    finally:
        show_cursor()


if __name__ == "__main__":
    main()
