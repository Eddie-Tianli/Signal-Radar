from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.topics.router import router as topics_router
from app.collection.router import router as collection_router
from app.ai.router import router as ai_router
from app.digests.router import router as digests_router
from app.scheduler.lifecycle import lifespan
from app.health import dependency_status
from app.notifications.service import notifications_enabled


app = FastAPI(title="SignalRadar API", version="0.0.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(topics_router)
app.include_router(collection_router)
app.include_router(ai_router)
app.include_router(digests_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": app.title,
        "version": app.version,
        "status": "running",
    }


@app.get("/api/status")
def read_status() -> dict[str, str]:
    return {**read_root(), **dependency_status(),
            "scheduler": "enabled" if getattr(app.state, "scheduler_enabled", False) else "disabled",
            "notifications": "enabled" if notifications_enabled() else "disabled"}
