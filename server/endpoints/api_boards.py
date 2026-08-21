from aiohttp import web

from server.board_handlers import api_boards_list, api_boards_create, api_boards_get, api_boards_update, \
    api_boards_delete, api_boards_save_layout

def add_routes(app: web.Application):
    # Boards API
    app.router.add_get("/api/boards", api_boards_list)
    app.router.add_post("/api/boards", api_boards_create)
    app.router.add_get("/api/boards/{id}", api_boards_get)
    app.router.add_post("/api/boards/{id}", api_boards_update)
    app.router.add_post("/api/boards/{id}/delete", api_boards_delete)
    app.router.add_post("/api/boards/{id}/layout", api_boards_save_layout)

    return app