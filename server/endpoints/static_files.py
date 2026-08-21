from pathlib import Path

from aiohttp.web_fileresponse import FileResponse
from aiohttp.web_response import Response

from aiohttp import web

from server.tools import _ctx, _error

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


async def index_handler(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def reports_handler(request: web.Request) -> Response | FileResponse:
    report_path = request.match_info["path"]
    reports_dir = Path(_ctx(request).reports_dir).resolve()
    target = (reports_dir / report_path).resolve()
    if not target.is_relative_to(reports_dir):
        return _error("Forbidden", status=403)
    if not target.exists() or target.is_dir():
        return _error("Not found", status=404)
    return web.FileResponse(target)


def add_routes(app: web.Application):
    # Static files
    app.router.add_get("/", index_handler)
    app.router.add_static("/static", STATIC_DIR)
    app.router.add_get("/reports/{path:.*}", reports_handler)
    return app
