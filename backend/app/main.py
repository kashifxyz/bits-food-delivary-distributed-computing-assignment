import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config.settings import settings
from backend.app.distributed.process_manager import process_manager
from backend.app.api.routes_processes import router as processes_router
from backend.app.api.routes_orders import router as orders_router
from backend.app.api.routes_events import router as events_router
from backend.app.api.routes_snapshot import router as snapshot_router
from backend.app.api.routes_scenarios import router as scenarios_router
from backend.app.api.websocket import router as ws_router

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DistributedFoodDelivery")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start async background channel listeners
    logger.info("Initializing Distributed System Processes (P1-P4)...")
    await process_manager.start()
    yield
    # Shutdown: Clean up tasks
    logger.info("Shutting down Distributed System Processes...")
    await process_manager.stop()

app = FastAPI(
    title="Distributed Food Delivery System Monitor",
    description="Distributed System Monitor for Event Tracking, Vector Clocks, and Chandy-Lamport Global Snapshots",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(processes_router)
app.include_router(orders_router)
app.include_router(events_router)
app.include_router(snapshot_router)
app.include_router(scenarios_router)
app.include_router(ws_router)

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "Distributed System Monitor",
        "processes_count": len(process_manager.processes),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
