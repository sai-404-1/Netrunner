from __future__ import annotations

import json
from typing import Any

from aiohttp import web

from server.tools import _ctx, _json_response, _read_json



def _require_auth(request: web.Request) -> dict:
    user = request.get("auth_user")
    if not user:
        raise web.HTTPUnauthorized(
            body=json.dumps({"ok": False, "error": "Authentication required"}, ensure_ascii=False),
            content_type="application/json",
        )
    return user


def _board_safe(board) -> dict:
    return {
        "id": board.id,
        "name": board.name,
        "owner_user_id": board.owner_user_id,
        "width": board.width,
        "height": board.height,
        "created_at": board.created_at,
        "updated_at": board.updated_at,
    }


async def api_boards_list(request: web.Request) -> web.Response:
    user = _require_auth(request)
    db = _ctx(request).db
    if user.get("is_superuser"):
        user_id_filter = request.rel_url.query.get("user_id")
        if user_id_filter:
            boards = db.boards.by_owner(int(user_id_filter))
        else:
            boards = db.boards.all_boards()
    else:
        boards = db.boards.by_owner(int(user["id"]))
    return _json_response({"ok": True, "data": [_board_safe(b) for b in boards]})


async def api_boards_create(request: web.Request) -> web.Response:
    user = _require_auth(request)
    payload = await _read_json(request)
    db = _ctx(request).db
    name = str(payload.get("name") or "").strip()
    if not name:
        return _json_response({"ok": False, "error": "name required"}, status=400)
    if user.get("is_superuser") and payload.get("owner_user_id"):
        owner_id = int(payload["owner_user_id"])
    else:
        owner_id = int(user["id"])
    width = int(payload.get("width") or 1600)
    height = int(payload.get("height") or 900)
    board = db.boards.create_board(name=name, owner_user_id=owner_id, width=width, height=height)
    return _json_response({"ok": True, "data": _board_safe(board)}, status=201)


async def api_boards_get(request: web.Request) -> web.Response:
    user = _require_auth(request)
    board_id = int(request.match_info["id"])
    db = _ctx(request).db
    result = db.boards.get_with_hosts(board_id)
    if result is None:
        return _json_response({"ok": False, "error": "Board not found"}, status=404)
    board = result["board"]
    if not user.get("is_superuser") and board.owner_user_id != int(user["id"]):
        return _json_response({"ok": False, "error": "Access denied"}, status=403)
    return _json_response({"ok": True, "data": {**_board_safe(board), "placements": result["placements"]}})


async def api_boards_update(request: web.Request) -> web.Response:
    user = _require_auth(request)
    board_id = int(request.match_info["id"])
    payload = await _read_json(request)
    db = _ctx(request).db
    board = db.boards.get(board_id)
    if board is None:
        return _json_response({"ok": False, "error": "Board not found"}, status=404)
    if not user.get("is_superuser") and board.owner_user_id != int(user["id"]):
        return _json_response({"ok": False, "error": "Access denied"}, status=403)
    update_data = {}
    if "name" in payload and str(payload["name"]).strip():
        update_data["name"] = str(payload["name"]).strip()
    if "width" in payload:
        update_data["width"] = int(payload["width"])
    if "height" in payload:
        update_data["height"] = int(payload["height"])
    if update_data:
        board = db.boards.update(board_id, **update_data)
    return _json_response({"ok": True, "data": _board_safe(board)})


async def api_boards_delete(request: web.Request) -> web.Response:
    user = _require_auth(request)
    board_id = int(request.match_info["id"])
    db = _ctx(request).db
    board = db.boards.get(board_id)
    if board is None:
        return _json_response({"ok": False, "error": "Board not found"}, status=404)
    if not user.get("is_superuser") and board.owner_user_id != int(user["id"]):
        return _json_response({"ok": False, "error": "Access denied"}, status=403)
    db.boards.delete(board_id)
    return _json_response({"ok": True})


async def api_boards_save_layout(request: web.Request) -> web.Response:
    user = _require_auth(request)
    board_id = int(request.match_info["id"])
    payload = await request.json()
    if not isinstance(payload, list):
        return _json_response({"ok": False, "error": "Expected a list of {host_id, x, y}"}, status=400)
    db = _ctx(request).db
    board = db.boards.get(board_id)
    if board is None:
        return _json_response({"ok": False, "error": "Board not found"}, status=404)
    if not user.get("is_superuser") and board.owner_user_id != int(user["id"]):
        return _json_response({"ok": False, "error": "Access denied"}, status=403)
    db.boards.save_layout(board_id, payload)
    return _json_response({"ok": True})
