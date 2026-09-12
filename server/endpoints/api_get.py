from aiohttp import web

from server.domens.hosts import api_hosts, api_hosts_status
from server.domens.host_profile import api_host_profile, api_host_metrics
from server.domens.summary import api_summary
from server.domens.groups import api_groups
from server.domens.modules import api_modules
from server.domens.tasks import api_task_runs, api_task_run_status
from server.domens.inventory import api_inventory
from server.domens.scheduled import api_scheduled
from server.domens.reports import api_reports
from server.domens.system import api_system_logs
from server.domens.ssh import api_ssh_keys
from server.domens.history import api_history_entries, api_history_entry, api_history_types
from server.domens.default_creds import api_default_creds_get


def add_routes(app: web.Application):
    # API GET
    app.router.add_get("/api/summary", api_summary)
    app.router.add_get("/api/hosts", api_hosts)
    app.router.add_get("/api/hosts/status", api_hosts_status)
    app.router.add_get("/api/hosts/{id}/profile", api_host_profile)
    app.router.add_get("/api/hosts/{id}/metrics", api_host_metrics)
    app.router.add_get("/api/groups", api_groups)
    app.router.add_get("/api/modules", api_modules)
    app.router.add_get("/api/task-runs", api_task_runs)
    app.router.add_get("/api/run/{id}/status", api_task_run_status)
    app.router.add_get("/api/inventory", api_inventory)
    app.router.add_get("/api/scheduled", api_scheduled)
    app.router.add_get("/api/reports", api_reports)
    app.router.add_get("/api/system-logs", api_system_logs)
    app.router.add_get("/api/ssh-keys", api_ssh_keys)
    app.router.add_get("/api/history", api_history_entries)
    app.router.add_get("/api/history/types", api_history_types)
    app.router.add_get("/api/history/{entry_id}", api_history_entry)
    app.router.add_get("/api/default-creds", api_default_creds_get)

    return app