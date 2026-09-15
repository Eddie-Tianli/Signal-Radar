"""Windows local launcher: one Uvicorn process and one Next production server."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from threading import Thread
import time

import httpx
import uvicorn
from sqlalchemy import text
from app.database import get_engine
from app.health import dependency_status, log_dependencies

ROOT = Path(__file__).resolve().parents[1]


def preflight():
    status = dependency_status()
    log_dependencies(status)
    if status["database"] != "connected":
        logging.error("PostgreSQL unavailable. Start the local PostgreSQL service and check backend/.env.")
        return False
    try:
        with get_engine().connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0004":
            raise ValueError
    except Exception:
        logging.error("Database migrations missing or outdated. Run python -m alembic upgrade head from backend/.")
        return False
    for port in (8000, 3000):
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
        except OSError:
            logging.error("Port %s is in use. Stop the existing server before launching another instance.", port)
            return False
    return True


def configure_logging():
    folder = ROOT.parent / "logs"
    folder.mkdir(exist_ok=True)
    handler = RotatingFileHandler(folder / "signalradar.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


def run():
    configure_logging()
    if not preflight():
        return 1
    frontend = ROOT.parent / "frontend"
    node = shutil.which("node")
    if not node or not (frontend / ".next/BUILD_ID").exists():
        logging.error("Node.js or frontend production build missing. Run start-signalradar.ps1.")
        return 1
    child = subprocess.Popen([node, str(frontend / "node_modules/next/dist/bin/next"),
                              "start", "--hostname", "127.0.0.1", "--port", "3000"],
                             cwd=frontend, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace",
                             creationflags=subprocess.CREATE_NO_WINDOW)
    def stream():
        for line in child.stdout:
            logging.info("Frontend: %s", line.rstrip())
    reader = Thread(target=stream, name="frontend-logs", daemon=True)
    reader.start()
    try:
        with httpx.Client(trust_env=False, timeout=1) as client:
            for _ in range(30):
                if child.poll() is not None:
                    logging.error("Frontend stopped during startup.")
                    return 1
                try:
                    if client.get("http://127.0.0.1:3000").is_success:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(1)
            else:
                logging.error("Frontend did not become ready. Check logs.")
                return 1
        logging.info("Open http://localhost:3000 - press Ctrl+C to stop both servers.")
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_config=None)
        return 0
    finally:
        if child.poll() is None:
            # Only the frontend process started here and its child workers are stopped.
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            child.wait(timeout=10)
        reader.join(timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        sys.exit((0 if preflight() else 1) if args.check else run())
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.error("Local startup failed. Check dependencies and configuration; no system settings were changed.")
        sys.exit(1)
