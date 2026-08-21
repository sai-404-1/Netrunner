import uuid
from pathlib import Path

from aiohttp import web

from server.tools import _require_admin, _error, _ctx, _ok, _safe_int, _read_json


def _uploads_dir() -> Path:
    try:
        from config import UPLOADS_PATH
    except Exception:
        UPLOADS_PATH = "uploads"
    directory = Path(UPLOADS_PATH)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _upload_to_dict(row) -> dict:
    return {
        "id": row.id,
        "name": row.original_name,
        "size_bytes": row.size_bytes,
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at,
    }


async def api_uploads_list(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    rows = _ctx(request).db.uploaded_files.recent(500)
    return _ok([_upload_to_dict(r) for r in rows])


async def api_uploads_create(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    ctx = _ctx(request)
    user = request.get("auth_user")
    uploaded_by = user.get("username") if user else None
    uploads_dir = _uploads_dir()

    reader = await request.multipart()
    saved = []
    async for part in reader:
        filename = part.filename
        if not filename:
            await part.read()  # сливаем не-файловые поля
            continue
        safe = Path(filename).name or "file"
        target = uploads_dir / f"{uuid.uuid4().hex}_{safe}"
        size = 0
        with target.open("wb") as fh:
            while True:
                chunk = await part.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                fh.write(chunk)
        row = ctx.db.uploaded_files.create(
            original_name=safe,
            stored_path=str(target),
            size_bytes=size,
            uploaded_by=uploaded_by,
        )
        saved.append(_upload_to_dict(row))

    if not saved:
        return _error("Файлы не получены", status=400)
    return _ok(saved)


async def api_uploads_download(request: web.Request) -> web.FileResponse | web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    row = _ctx(request).db.uploaded_files.get(_safe_int(request.match_info["id"]))
    if not row:
        return _error("Файл не найден", status=404)
    target = Path(row.stored_path)
    if not target.exists():
        return _error("Файл отсутствует на диске", status=404)
    return web.FileResponse(
        target,
        headers={"Content-Disposition": f'attachment; filename="{row.original_name}"'},
    )


async def api_uploads_delete(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _error("Только для администратора", status=403)
    ctx = _ctx(request)
    payload = await _read_json(request)
    file_id = _safe_int(payload.get("id"))
    row = ctx.db.uploaded_files.get(file_id)
    if not row:
        return _error("Файл не найден", status=404)
    try:
        Path(row.stored_path).unlink(missing_ok=True)
    except OSError:
        pass
    ctx.db.uploaded_files.delete(file_id)
    return _ok({"deleted": file_id})