# Сгенерировано нейросетью
import sys
import termios
import tty

CSI = "\x1b["

def flush():
    sys.stdout.flush()

def get_cursor_position():
    """
    Возвращает позицию курсора как (x, y), где:
    x — колонка, 0-based
    y — строка, 0-based

    Работает в ANSI-совместимом терминале.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise OSError("stdin/stdout не являются терминалом")

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)

        # Запрос позиции курсора
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()

        response = ""
        while True:
            ch = sys.stdin.read(1)
            response += ch
            if ch == "R":
                break

        # Ожидаем ответ вида: ESC[row;colR
        if not response.startswith("\x1b[") or not response.endswith("R"):
            raise ValueError(f"Неожиданный ответ терминала: {response!r}")

        body = response[2:-1]  # убираем ESC[ и R
        row, col = map(int, body.split(";"))

        # Переводим в 0-based
        return col - 1, row - 1

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def move_to(x: int, y: int):
    """
    Переместить курсор в позицию x, y.
    x, y -> 0-based
    """
    sys.stdout.write(f"{CSI}{y + 1};{x + 1}H")

def write_at(x: int, y: int, text: str):
    move_to(x, y)
    sys.stdout.write(text)
    flush()

def clear_cell(x: int, y: int):
    """
    Очистить один символ в позиции x, y.
    """
    move_to(x, y)
    sys.stdout.write(" ")
    flush()

def clear_line(y: int):
    """
    Очистить всю строку y.
    """
    move_to(0, y)
    sys.stdout.write(f"{CSI}2K")
    flush()

def clear_lines(start_y: int, count: int):
    for y in range(start_y, start_y + count):
        clear_line(y)

def clear_screen():
    sys.stdout.write(f"{CSI}2J{CSI}H")
    flush()

def hide_cursor():
    sys.stdout.write(f"{CSI}?25l")
    flush()

def show_cursor():
    sys.stdout.write(f"{CSI}?25h")
    flush()