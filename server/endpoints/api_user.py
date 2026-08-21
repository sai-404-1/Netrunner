from aiohttp import web

from server.auth_handlers import (
    api_login,
    api_login_verify,
    api_logout,
    api_me,
    api_me_update,
    api_register,
)

def add_routes(app: web.Application):
    # Public authentication endpoints
    app.router.add_post("/api/login", api_login)
    app.router.add_post("/api/login/verify", api_login_verify)
    app.router.add_post("/api/register", api_register)
    app.router.add_post("/api/logout", api_logout)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/me/update", api_me_update)

    return app