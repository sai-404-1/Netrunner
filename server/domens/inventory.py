from aiohttp import web

from server.tools import _ok, _ctx

async def api_inventory(request: web.Request) -> web.Response:
    return _ok(_ctx(request).db.inventory.all(order_by="collected_at DESC"))