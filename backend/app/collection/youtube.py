import os
from html import unescape
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from app.collection.source import SourceAdapter
from app.items.schemas import NormalizedItem


class SourceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class YouTubeSource(SourceAdapter):
    def __init__(self, client: httpx.Client, api_key: str):
        self.client = client
        self.api_key = api_key.strip()

    def search(self, query: str) -> list[NormalizedItem]:
        if not self.api_key:
            raise SourceError("YouTube is not configured: set YOUTUBE_API_KEY on the backend.", 503)
        try:
            response = self.client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "type": "video", "q": query, "maxResults": 15, "key": self.api_key},
                timeout=15.0,
            )
        except httpx.TimeoutException:
            raise SourceError("YouTube request timed out. Try again later.", 504) from None
        except httpx.RequestError:
            raise SourceError("Could not connect to YouTube. Try again later.") from None
        if response.status_code == 403:
            raise SourceError("YouTube rejected the request. Check API enablement, key restrictions, and quota.")
        if not response.is_success:
            raise SourceError("YouTube request failed. Check API configuration or try again later.")
        try:
            payload = response.json()
            entries = payload["items"]
            if not isinstance(entries, list) or len(entries) > 15:
                raise ValueError("Invalid result list")
            results = []
            for entry in entries:
                video_id = entry["id"]["videoId"]
                if not isinstance(video_id, str) or not video_id.strip():
                    raise ValueError("Missing video ID")
                snippet = entry["snippet"]
                results.append(NormalizedItem(
                    source="youtube", external_id=video_id,
                    title=unescape(snippet["title"]),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    author=unescape(snippet["channelTitle"]) if snippet.get("channelTitle") else None,
                    published_at=snippet.get("publishedAt") or None,
                    snippet=unescape(snippet["description"]) if snippet.get("description") else None,
                ))
            return results
        except (ValueError, KeyError, TypeError, AttributeError, ValidationError):
            raise SourceError("YouTube returned an invalid search response.") from None


def get_youtube_source():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    with httpx.Client(follow_redirects=False) as client:
        yield YouTubeSource(client, os.getenv("YOUTUBE_API_KEY", ""))
