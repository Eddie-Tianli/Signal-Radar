from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.topics.router import router as topics_router
from app.collection.router import router as collection_router
from app.ai.router import router as ai_router
from app.digests.router import router as digests_router
from app.scheduler.lifecycle import lifespan
from app.health import dependency_status
from app.dashboard import router as dashboard_router
from app.notifications.service import notifications_enabled
from app.workflows.router import router as updates_router
from app.workflows.locks import TopicBusy
from app.trash.router import router as trash_router


app = FastAPI(title="SignalRadar API", version="0.2.0", lifespan=lifespan)
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
app.include_router(dashboard_router)
app.include_router(updates_router)
app.include_router(trash_router)


@app.exception_handler(TopicBusy)
async def topic_busy_handler(request, error):
    return JSONResponse(status_code=409, content={"detail": "Topic operation already running. Wait and refresh."})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request, error):
    logging.getLogger("uvicorn.error").error("Database operation failed (%s)", type(error).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database operation failed. Check the local database."})


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
