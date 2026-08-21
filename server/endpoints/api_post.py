from aiohttp import web

from server.domens.groups import api_groups_create, api_groups_update, api_groups_delete, api_groups_add_host
from server.domens.hosts import api_hosts_create, api_hosts_update, api_hosts_delete, api_hosts_check_all, \
    api_hosts_reprovision
from server.domens.modules import api_modules_create, api_modules_update, api_modules_delete
from server.domens.reports import api_reports_clear, api_reports_export
from server.domens.scheduled import api_schedule_create, api_active_scheduled, api_inactive_scheduled, \
    api_schedule_update, api_schedule_delete, api_scheduler_tick
from server.domens.ssh import api_ssh_keys_create, api_keys_generate
from server.domens.tasks import api_run, api_run_cancel, api_task_runs_clear
from server.domens.uploads import api_uploads_list, api_uploads_create, api_uploads_download, api_uploads_delete


def add_routes(app: web.Application):
    # HOSTS
    app.router.add_post("/api/hosts", api_hosts_create)
    app.router.add_post("/api/hosts/update", api_hosts_update)
    app.router.add_post("/api/hosts/delete", api_hosts_delete)
    app.router.add_post("/api/hosts/check", api_hosts_check_all)
    app.router.add_post("/api/hosts/check-all", api_hosts_check_all)
    app.router.add_post("/api/hosts/reprovision", api_hosts_reprovision)

    # FILE UPLOADS
    app.router.add_get("/api/uploads", api_uploads_list)
    app.router.add_post("/api/uploads", api_uploads_create)
    app.router.add_get("/api/uploads/{id}/download", api_uploads_download)
    app.router.add_post("/api/uploads/delete", api_uploads_delete)

    # GROUPS
    app.router.add_post("/api/groups", api_groups_create)
    app.router.add_post("/api/groups/update", api_groups_update)
    app.router.add_post("/api/groups/delete", api_groups_delete)
    app.router.add_post("/api/groups/add-host", api_groups_add_host)

    # TASK RUN
    app.router.add_post("/api/run", api_run)
    app.router.add_post("/api/run/{id}/cancel", api_run_cancel)

    # MODULES
    app.router.add_post("/api/modules", api_modules_create)
    app.router.add_post("/api/modules/update", api_modules_update)
    app.router.add_post("/api/modules/delete", api_modules_delete)

    # SCHEDULE
    app.router.add_post("/api/schedule", api_schedule_create)
    app.router.add_get("/api/schedule/active", api_active_scheduled)
    app.router.add_get("/api/schedule/inactive", api_inactive_scheduled)
    app.router.add_post("/api/schedule/update", api_schedule_update)
    app.router.add_post("/api/schedule/delete", api_schedule_delete)
    app.router.add_post("/api/scheduler/tick", api_scheduler_tick)

    # REPORTS
    app.router.add_post("/api/reports/clear", api_reports_clear)
    app.router.add_post("/api/reports/export", api_reports_export)

    # OTHER
    app.router.add_post("/api/task-runs/clear", api_task_runs_clear)
    app.router.add_post("/api/ssh-keys", api_ssh_keys_create)
    app.router.add_post("/api/keys/generate", api_keys_generate)

    return app