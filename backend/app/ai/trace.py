"""Opt-in, local-only Ollama diagnostics. Trace failures must never fail inference."""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
from threading import Lock
from urllib.parse import quote
from uuid import uuid4


TRACE_PATH = Path(__file__).resolve().parents[2] / "logs" / "ollama_trace.jsonl"
_write_lock = Lock()
log = logging.getLogger("uvicorn.error")
_credential_name = re.compile(
    r"authorization|password|passwd|secret|credential|(?:^|[_-])(?:api[_-]?key|token|access[_-]?key)(?:$|[_-])",
    re.I,
)


class OllamaTrace:
    def __init__(self, stage: str, item_count: int | None):
        self.enabled = os.getenv("OLLAMA_TRACE_ENABLED", "false").strip().lower() == "true"
        self.stage, self.item_count = stage, item_count
        self.call_id = uuid4().hex
        self.request_id = None
        self.parent_request_id = None
        self.attempt = 0
        self.secrets = set()

    def start_attempt(self, attempt: int):
        self.parent_request_id = self.request_id
        self.request_id = uuid4().hex
        self.attempt = attempt

    def _redact(self, value):
        if isinstance(value, dict):
            return {key: "[REDACTED]" if _credential_name.search(str(key)) else self._redact(item)
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._redact(item) for item in value]
        if not isinstance(value, str):
            return value
        for secret in sorted(self.secrets, key=len, reverse=True):
            if not secret:
                continue
            encoded_forms = set()
            # Request/response bodies can contain JSON strings within JSON strings.
            for seed in (secret, json.dumps(secret, ensure_ascii=True)[1:-1], quote(secret, safe="")):
                encoded = seed
                while encoded not in encoded_forms and len(encoded) <= len(value):
                    encoded_forms.add(encoded)
                    encoded = json.dumps(encoded, ensure_ascii=False)[1:-1]
            for encoded in sorted(encoded_forms, key=len, reverse=True):
                value = value.replace(encoded, "[REDACTED]")
        value = re.sub(r"(?i)\b(?:bearer|basic)\s+[a-zA-Z0-9._~+/=-]+", "[REDACTED]", value)
        value = re.sub(r"(?i)\bsk-[a-zA-Z0-9_-]+|\bAIza[a-zA-Z0-9_-]+", "[REDACTED]", value)
        value = re.sub(
            r'''(?ix)(\b(?:authorization|password|passwd|secret|api[_\ -]?key|(?:access[_-]|refresh[_-])?token)\b["']?\s*[:=]\s*)
                (?:"[^"]*"|'[^']*'|[^\s,;}]+)''',
            r"\1[REDACTED]", value,
        )
        return value

    def _write(self, event, fields):
        # Read credential values only for redaction; never serialize the environment.
        self.secrets.update(value for key, value in os.environ.items()
                            if value and _credential_name.search(key))
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_id": self.call_id, "request_id": self.request_id,
            "parent_request_id": self.parent_request_id,
            "stage": self.stage, "attempt": self.attempt,
            "item_count": self.item_count, "event": event, **fields,
        }
        line = json.dumps(self._redact(record), ensure_ascii=False) + "\n"
        with _write_lock:
            TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with TRACE_PATH.open("a", encoding="utf-8") as output:
                output.write(line)

    def _guard(self, operation):
        if not self.enabled:
            return
        try:
            operation()
        except Exception:
            # Never log the exception text: file paths/content may contain secrets.
            try:
                log.warning("Ollama trace write failed; inference continues")
            except Exception:
                pass

    def emit(self, event, **fields):
        self._guard(lambda: self._write(event, fields))

    def request(self, request):
        def record():
            # Use the built HTTP request bytes, not a prompt template or draft payload.
            # Headers are not logged; credential values are retained only for redaction.
            for key, value in request.headers.items():
                if value and (_credential_name.search(key) or key.lower() == "cookie"):
                    self.secrets.add(value)
                    if key.lower() in ("authorization", "proxy-authorization"):
                        token = value.split(" ", 1)[-1]
                        if token:
                            self.secrets.add(token)
            raw = request.content.decode("utf-8")
            payload = json.loads(raw)
            messages = payload.get("messages", [])
            self._write("request", {
                "endpoint": request.url.path, "model": payload.get("model"),
                "request_body": raw, "payload": payload,
                "messages": messages,
                "system_message": [m.get("content") for m in messages if m.get("role") == "system"],
                "user_message": [m.get("content") for m in messages if m.get("role") == "user"],
                "prompt": messages,
                "format": payload.get("format"), "options": payload.get("options"),
                "temperature": payload.get("options", {}).get("temperature"),
                "stream": payload.get("stream"),
            })
        self._guard(record)

    def response(self, response, elapsed_ms):
        def record():
            # Persist the raw body before attempting any response JSON decoding.
            self._write("response", {"status_code": response.status_code,
                                     "elapsed_ms": elapsed_ms, "raw_response": response.text})
            try:
                payload = response.json()
            except (ValueError, TypeError):
                return  # The provider records the response_structure_error.
            fields = {"response_json": payload}
            if isinstance(payload, dict):
                message = payload.get("message")
                fields.update({
                    "content": message.get("content") if isinstance(message, dict) else None,
                    "model": payload.get("model"),
                    "statistics": {key: value for key, value in payload.items()
                                   if key.endswith(("_count", "_duration")) or key in ("done", "done_reason", "created_at")},
                })
            self._write("response_details", fields)
        self._guard(record)
