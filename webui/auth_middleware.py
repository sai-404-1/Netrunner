from __future__ import annotations

import json

from aiohttp import web


# Public paths that do not require authentication.
_PUBLIC_PATHS = {
    "/api/login",
    "/api/register",
}


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    if path.startswith("/api/login") or path.startswith("/api/register"):
        return True
    return False


@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Require a valid API token for all non-public API routes."""
    path = request.path

    # Static files and Next.js pages (when front/back share a server) are not
    # protected here; the Next.js app handles its own session/auth layer.
    if not path.startswith("/api") or _is_public(path):
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.query.get("token", "")
    if not token:
        token = request.cookies.get("netrunner_token", "")

    auth_service = request.app.get("auth_service")
    if auth_service is None:
        return await handler(request)

    user = auth_service.me(token)
    if user is None:
        return web.Response(
            body=json.dumps({"ok": False, "error": "not authenticated"}, ensure_ascii=False),
            status=401,
            content_type="application/json",
            charset="utf-8",
        )

    request["auth_user"] = user
    return await handler(request)
