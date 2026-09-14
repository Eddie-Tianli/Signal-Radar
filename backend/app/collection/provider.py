import os
from pathlib import Path

from dotenv import load_dotenv

from app.collection.mock import MockSource
from app.collection.youtube import get_youtube_source


def get_source():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if os.getenv("USE_MOCK_SOURCE", "false").strip().lower() == "true":
        yield MockSource()
    else:
        yield from get_youtube_source()
