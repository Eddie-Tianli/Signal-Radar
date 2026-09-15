import asyncio
import math
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread
from dotenv import load_dotenv
from app.scheduler.runner import run_cycle, log


class LocalScheduler:
    def __init__(self, interval_seconds, job=run_cycle):
        self.interval = interval_seconds
        self.job = job
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread is not None:
            return
        self.thread = Thread(target=self._loop, name="signalradar-scheduler", daemon=False)
        self.thread.start()
        log.info("Scheduler started interval_seconds=%s", self.interval)

    def _loop(self):
        while not self.stop_event.wait(self.interval):
            self.job(stop=self.stop_event)

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join()
        log.info("Scheduler stopped")


def configured_scheduler():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    # TestClient must never start background jobs, even with a developer's enabled .env.
    if "pytest" in sys.modules or os.getenv("SCHEDULER_ENABLED", "false").strip().lower() != "true":
        return None
    try:
        minutes = float(os.getenv("SCAN_INTERVAL_MINUTES", "60"))
        if not math.isfinite(minutes) or not 0.1 <= minutes <= 10080:
            raise ValueError
    except ValueError:
        raise RuntimeError("SCAN_INTERVAL_MINUTES must be between 0.1 and 10080.") from None
    return LocalScheduler(minutes * 60)


@asynccontextmanager
async def lifespan(app):
    scheduler = configured_scheduler()
    if scheduler:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            await asyncio.to_thread(scheduler.stop)
