from aiohttp import web

async def healthz_handler(request: web.Request) -> web.Response:
    """Публичный health-check для супервизора (см. supervise.py)."""
    return web.json_response({"ok": True})

def add_routes(app: web.Application):
    # Health check (public, used by the supervisor)
    app.router.add_get("/healthz", healthz_handler)
    return app