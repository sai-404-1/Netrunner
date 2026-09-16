from aiohttp import web

from server.domens.scenarios import api_scenarios_list, api_scenarios_runs, api_scenarios_run_status, \
    api_scenarios_create, api_scenarios_run, api_scenarios_delete, api_scenarios_update, \
    api_scenarios_move, api_scenario_folders_list, api_scenario_folders_create, \
    api_scenario_folders_update, api_scenario_folders_delete

def add_routes(app: web.Application):
    # Scenarios API
    app.router.add_get("/api/scenarios", api_scenarios_list)
    app.router.add_get("/api/scenarios/runs", api_scenarios_runs)
    app.router.add_get("/api/scenarios/runs/{id}", api_scenarios_run_status)
    app.router.add_post("/api/scenarios", api_scenarios_create)
    app.router.add_post("/api/scenarios/update", api_scenarios_update)
    app.router.add_post("/api/scenarios/run", api_scenarios_run)
    app.router.add_post("/api/scenarios/delete", api_scenarios_delete)
    app.router.add_post("/api/scenarios/move", api_scenarios_move)

    # Папки сценариев: читают все, меняет только суперпользователь.
    app.router.add_get("/api/scenario-folders", api_scenario_folders_list)
    app.router.add_post("/api/scenario-folders", api_scenario_folders_create)
    app.router.add_post("/api/scenario-folders/update", api_scenario_folders_update)
    app.router.add_post("/api/scenario-folders/delete", api_scenario_folders_delete)

    return app