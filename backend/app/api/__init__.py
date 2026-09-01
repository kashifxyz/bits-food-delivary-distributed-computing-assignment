from backend.app.api.routes_processes import router as processes_router
from backend.app.api.routes_orders import router as orders_router
from backend.app.api.routes_events import router as events_router
from backend.app.api.routes_snapshot import router as snapshot_router
from backend.app.api.routes_scenarios import router as scenarios_router
from backend.app.api.websocket import router as ws_router

__all__ = [
    "processes_router",
    "orders_router",
    "events_router",
    "snapshot_router",
    "scenarios_router",
    "ws_router",
]
