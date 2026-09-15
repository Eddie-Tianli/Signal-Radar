import json
import logging
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from dotenv import load_dotenv

log = logging.getLogger("uvicorn.error")


class NotificationService(ABC):
    @abstractmethod
    def send(self, topic_name: str, relevant_count: int) -> None:
        """Notify after a successful automatic Digest; never perform business writes."""
        raise NotImplementedError


class WindowsNotificationService(NotificationService):
    def send(self, topic_name: str, relevant_count: int) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows notifications require an interactive Windows session")
        # Data goes through stdin JSON, never interpolated into PowerShell source.
        payload = json.dumps({"topic": topic_name[:160], "count": relevant_count})
        script = Path(__file__).with_name("toast.ps1")
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-File", str(script)],
                       input=payload, text=True, capture_output=True, timeout=10, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)


def notifications_enabled():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    return os.getenv("NOTIFICATIONS_ENABLED", "false").strip().lower() == "true"


def get_notification_service():
    return WindowsNotificationService() if notifications_enabled() else None


def notify_safely(topic_id, topic_name, relevant_count, service_factory=get_notification_service):
    try:
        service = service_factory()
        if service is not None:
            service.send(topic_name, relevant_count)
            log.info("Topic %s Notification sent", topic_id)
    except Exception:
        log.warning("Topic %s Notification failed", topic_id)
