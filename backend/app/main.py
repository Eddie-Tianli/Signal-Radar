from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="SignalRadar API", version="0.0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
)


@app.get("/")
@app.get("/api/status")
def read_root() -> dict[str, str]:
    return {
        "name": app.title,
        "version": app.version,
        "status": "running",
    }
