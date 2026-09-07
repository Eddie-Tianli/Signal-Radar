from fastapi import FastAPI


app = FastAPI(title="SignalRadar API", version="0.0.1")


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": app.title,
        "version": app.version,
        "status": "running",
    }
