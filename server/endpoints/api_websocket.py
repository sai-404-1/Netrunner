from aiohttp import web

from server.domens.websocket import websocket_handler, agent_websocket_handler
# from server.server import websocket_handler, agent_websocket_handler
from server.terminal_handler import api_terminal_ws

def add_routes(app: web.Application):
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/agent/ws", agent_websocket_handler)
    app.router.add_get("/api/terminal/ws", api_terminal_ws)

    return app