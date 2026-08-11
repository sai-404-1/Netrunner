from __future__ import annotations

import argparse
import logging

from services.app_context import create_app_context
from server.server import run_web_server


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Запуск server-GUI NetRunner")
    parser.add_argument("--host", default="127.0.0.1", help="Адрес server-сервера")
    parser.add_argument("--port", type=int, default=8000, help="Порт server-сервера")
    parser.add_argument("--db", default="data/netrunner.db", help="Путь к SQLite базе данных")
    parser.add_argument("--reports", default="reports", help="Каталог для отчётов")
    parser.add_argument("--open-browser", action="store_true", help="Открыть браузер после запуска")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ctx = create_app_context(db_path=args.db, reports_dir=args.reports)
    try:
        run_web_server(
            app_context=ctx,
            host=args.host,
            port=args.port,
            open_browser=args.open_browser,
        )
    except KeyboardInterrupt:
        print("\nОстановка server-GUI...")
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
