from aiohttp import web

from server.domens.devices import api_me_devices_list, api_me_devices_trust, api_me_devices_revoke
from server.domens.telegram import api_me_telegram_status, api_me_telegram_link, api_me_telegram_unlink, \
    api_admin_telegram_get, api_admin_telegram_set
from server.domens.update import api_update_check, api_update_diff, api_update_pull, api_update_status, \
    api_update_recheck, api_update_set_config, api_update_apply, api_update_incidents


# from server.server import api_update_check, api_update_diff, api_update_pull, api_update_status, api_update_recheck, \
#     api_update_set_config, api_update_apply, api_update_incidents, api_me_telegram_status, api_me_telegram_link, \
#     api_me_telegram_unlink, api_admin_telegram_get, api_admin_telegram_set, api_me_devices_list, api_me_devices_trust, \
#     api_me_devices_revoke


def add_routes(app: web.Application):
    # UPDATE
    app.router.add_get("/api/update/check", api_update_check)
    app.router.add_get("/api/update/diff", api_update_diff)
    app.router.add_post("/api/update/pull", api_update_pull)
    app.router.add_get("/api/update/status", api_update_status)
    app.router.add_post("/api/update/recheck", api_update_recheck)
    app.router.add_post("/api/update/config", api_update_set_config)
    app.router.add_post("/api/update/apply", api_update_apply)
    app.router.add_get("/api/update/incidents", api_update_incidents)

    # TELEGRAM
    app.router.add_get("/api/me/telegram/status", api_me_telegram_status)
    app.router.add_post("/api/me/telegram/link", api_me_telegram_link)
    app.router.add_post("/api/me/telegram/unlink", api_me_telegram_unlink)
    app.router.add_get("/api/admin/telegram", api_admin_telegram_get)
    app.router.add_post("/api/admin/telegram", api_admin_telegram_set)

    # DEVICES
    app.router.add_get("/api/me/devices", api_me_devices_list)
    app.router.add_post("/api/me/devices/trust", api_me_devices_trust)
    app.router.add_post("/api/me/devices/revoke", api_me_devices_revoke)

    return app

