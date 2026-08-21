import asyncio

from aiohttp import web

from server.tools import _ok, _ctx, model_to_dict, _read_json, _error
from services.host_service import _generate_ssh_key, _write_generated_ssh_key


async def api_ssh_keys(request: web.Request) -> web.Response:
    keys = []
    for key in _ctx(request).db.ssh_keys.all():
        item = model_to_dict(key)
        item.pop("private_key", None)
        keys.append(item)
    return _ok(keys)


async def api_ssh_keys_create(request: web.Request) -> web.Response:
    db = _ctx(request).db
    payload = await _read_json(request)
    name = str(payload.get("name") or "").strip()
    file_data = payload.get("file_data")
    if not name:
        return _error("SSH key name is required")
    if not file_data:
        return _error("SSH key file data is required")
    private_path = _save_ssh_key(name, file_data)
    public_path = private_path.with_suffix(".pub")
    public_key_path = str(public_path) if public_path.exists() else None
    key = db.ssh_keys.create(
        name=name,
        private_key_path=str(private_path),
        public_key_path=public_key_path,
        has_passphrase=0,
        is_default=0,
    )
    return _ok(key)


async def api_keys_generate(request: web.Request) -> web.Response:
    db = _ctx(request).db
    payload = await _read_json(request)
    name = str(payload.get("key_name") or "").strip()
    key_type = str(payload.get("key_type") or "").strip().lower()
    passphrase = str(payload.get("passphrase") or "").strip() or None
    if not name:
        return _error("SSH key name is required")
    if key_type not in ("rsa", "ed25519"):
        return _error("key_type must be rsa or ed25519")

    private_pem, public_openssh, fingerprint, has_passphrase = await asyncio.to_thread(
        _generate_ssh_key, key_type, passphrase
    )
    private_path, public_path = _write_generated_ssh_key(name, private_pem, public_openssh)
    # The private key is stored only in the encrypted file on disk; the plaintext
    # private key material is intentionally not persisted in the database so it
    # cannot be leaked through API responses or backups.
    key = db.ssh_keys.create(
        name=name,
        private_key_path=str(private_path),
        public_key_path=str(public_path),
        key_type=key_type,
        public_key=public_openssh,
        fingerprint=fingerprint,
        has_passphrase=has_passphrase,
        is_default=0,
    )
    return _ok(
        {
            "id": key.id,
            "name": key.name,
            "key_type": key.key_type,
            "public_key": key.public_key,
            "fingerprint": key.fingerprint,
            "created_at": key.created_at,
        }
    )