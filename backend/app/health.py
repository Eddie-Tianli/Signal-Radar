import logging
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx
from dotenv import load_dotenv
from sqlalchemy import text
from app.database import get_engine

log = logging.getLogger("uvicorn.error")


def dependency_status():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    result = {"database": "unavailable", "ollama": "unavailable"}
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        result["database"] = "connected"
    except Exception:
        pass
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        url = urlparse(base)
    except ValueError:
        return result
    if url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1") and not url.username and not url.password:
        try:
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=2) as client:
                response = client.get(base + "/api/tags")
                if response.is_success and isinstance(response.json().get("models"), list):
                    result["ollama"] = "available"
        except Exception:
            pass
    return result


def log_dependencies(status):
    log.info("Database %s", status["database"])
    if status["ollama"] == "available":
        log.info("Ollama available")
    else:
        log.warning("Ollama unavailable - AI analysis will fail until Ollama is started.")
