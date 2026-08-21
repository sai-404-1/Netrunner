from aiohttp import web

from server.tools import _ctx, _ok


async def api_summary(request: web.Request) -> web.Response:
    db = _ctx(request).db
    task_runs = db.task_runs.list_recent(10)
    inventory = db.inventory.all(order_by="collected_at DESC")
    reports = db.reports.latest(5)

    # Per-group stats
    all_hosts = db.hosts.all()
    all_groups = db.groups.all()
    group_stats = []
    for group in all_groups:
        hosts = db.groups.hosts(group.id)
        total = len(hosts)
        online = sum(1 for h in hosts if getattr(h, 'is_active', False))
        group_stats.append({
            "id": group.id,
            "name": group.name,
            "kind": group.kind,
            "total": total,
            "online": online,
            "offline": total - online,
        })

    data = {
        "hosts": len(all_hosts),
        "hosts_online": sum(1 for h in all_hosts if h.is_active),
        "groups": len(all_groups),
        "modules": len(db.modules.all()),
        "task_runs": len(db.task_runs.all()),
        "inventory": len(inventory),
        "scheduled": len(db.scheduled.all()),
        "reports": len(db.reports.all()),
        "recent_task_runs": task_runs,
        "latest_inventory": inventory[:5],
        "latest_reports": reports,
        "group_stats": group_stats,
    }
    return _ok(data)