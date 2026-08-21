import json

from aiohttp import web

from server.auth_middleware import auth_middleware
from server.tools import _json_response
from services.auth_service import AuthService

from . import api_admin, api_user, healthz, static_files, api_get, api_post, api_boards, api_scenarios, api_update, api_websocket

from services.logger import Logger

logger = Logger()

@web.middleware
async def error_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
        return response
    except web.HTTPException as exc:
        # Return JSON for every HTTP error so the JS frontend can parse it.
        error_text = exc.text or exc.reason or "HTTP error"
        try:
            # If the exception already carried a JSON body, reuse its message.
            payload = json.loads(error_text)
            if isinstance(payload, dict) and "ok" in payload:
                return _json_response(payload, status=exc.status)
        except (json.JSONDecodeError, TypeError):
            pass
        return _json_response({"ok": False, "error": error_text}, status=exc.status)
    except Exception as exc:
        logger.exception("Unhandled API error: %s", exc)
        return _json_response({"ok": False, "error": "Internal server error"}, status=500)

def build_app(app_context) -> web.Application:
    app = web.Application(middlewares=[auth_middleware, error_middleware])
    app["ctx"] = app_context
    app["auth_service"] = AuthService(app_context.db)
    app["websockets"] = set()
    app["background_tasks"] = set()

    app = api_admin.add_routes(app)
    app = api_user.add_routes(app)
    app = healthz.add_routes(app)
    app = static_files.add_routes(app)
    app = api_get.add_routes(app)
    app = api_post.add_routes(app)
    app = api_boards.add_routes(app)
    app = api_scenarios.add_routes(app)
    app = api_update.add_routes(app)
    app = api_websocket.add_routes(app)

    return app