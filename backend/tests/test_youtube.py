import httpx
import pytest

from app.collection.youtube import SourceError, YouTubeSource


def video(video_id="video-1"):
    return {"id": {"videoId": video_id}, "snippet": {
        "title": "Film &amp; News", "channelTitle": "Channel",
        "publishedAt": "2026-09-01T10:00:00Z", "description": "A description",
    }}


def test_youtube_mapping_and_single_request():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "www.googleapis.com"
        assert request.url.path == "/youtube/v3/search"
        assert dict(request.url.params) == {
            "part": "snippet", "type": "video", "q": "Nolan", "maxResults": "15", "key": "test-key",
        }
        return httpx.Response(200, json={"items": [video()], "nextPageToken": "ignored"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = YouTubeSource(client, "test-key").search("Nolan")[0]
    assert len(requests) == 1
    assert result.source == "youtube"
    assert result.external_id == "video-1"
    assert result.title == "Film & News"
    assert result.url == "https://www.youtube.com/watch?v=video-1"
    assert result.author == "Channel"
    assert result.snippet == "A description"
    assert result.published_at.utcoffset().total_seconds() == 0


def test_missing_key_does_not_call_network():
    def handler(request):
        pytest.fail("Missing key must not send a request")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError, match="YOUTUBE_API_KEY") as error:
            YouTubeSource(client, "  ").search("query")
        assert error.value.status_code == 503


@pytest.mark.parametrize("status", [400, 403, 429, 500])
def test_upstream_http_error_is_sanitized(status):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, text="private-key-secret")
    )) as client:
        with pytest.raises(SourceError) as error:
            YouTubeSource(client, "private-key-secret").search("query")
        assert error.value.status_code == 502
        assert "private-key-secret" not in str(error.value)


@pytest.mark.parametrize("exception,code", [(httpx.ReadTimeout, 504), (httpx.ConnectError, 502)])
def test_network_errors(exception, code):
    def handler(request):
        raise exception("private-key-secret", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError) as error:
            YouTubeSource(client, "private-key-secret").search("query")
        assert error.value.status_code == code
        assert "private-key-secret" not in str(error.value)


@pytest.mark.parametrize("payload", [{}, {"items": None}, {"items": [{}]}, {"items": [video(), {}]}])
def test_malformed_response(payload):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))) as client:
        with pytest.raises(SourceError, match="invalid search response"):
            YouTubeSource(client, "test-key").search("query")


def test_empty_search_results():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []}))) as client:
        assert YouTubeSource(client, "test-key").search("query") == []
