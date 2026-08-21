from aiohttp import web

from server.admin_handlers import api_admin_users_list, api_admin_users_create, api_admin_users_update, \
    api_admin_users_delete, api_admin_user_modules, api_admin_user_modules_set, api_admin_user_groups, \
    api_admin_user_groups_set, api_admin_db_tables, api_admin_backup, api_admin_restore, api_admin_host_agents, \
    api_admin_host_events


def add_routes(app: web.Application):
    # USERS
    app.router.add_get("/api/admin/users", api_admin_users_list)
    app.router.add_post("/api/admin/users", api_admin_users_create)
    app.router.add_post("/api/admin/users/update", api_admin_users_update)
    app.router.add_post("/api/admin/users/delete", api_admin_users_delete)

    # MODULES
    app.router.add_get("/api/admin/user-modules", api_admin_user_modules)
    app.router.add_post("/api/admin/user-modules", api_admin_user_modules_set)

    # GROUPS
    app.router.add_get("/api/admin/user-groups", api_admin_user_groups)
    app.router.add_post("/api/admin/user-groups", api_admin_user_groups_set)

    # DATABASE
    app.router.add_get("/api/admin/db-tables", api_admin_db_tables)
    app.router.add_get("/api/admin/backup", api_admin_backup)
    app.router.add_post("/api/admin/restore", api_admin_restore)

    # TODO проверить работу
    app.router.add_get("/api/admin/host-agents", api_admin_host_agents)
    app.router.add_get("/api/admin/host-events", api_admin_host_events)

    return app