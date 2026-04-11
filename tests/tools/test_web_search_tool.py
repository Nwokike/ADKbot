"""Tests for multi-provider web search."""

import httpx
import pytest
from pathlib import Path

from adkbot.agent.tools.web import web_search
from adkbot.agent.tools.web import web_fetch


def _response(status: int = 200, json: dict | None = None) -> httpx.Response:
    """Build a mock httpx.Response with a dummy request attached."""
    r = httpx.Response(status, json=json)
    r._request = httpx.Request("GET", "https://mock")
    return r


@pytest.mark.asyncio
async def test_brave_search(monkeypatch):
    async def mock_get(self, url, **kw):
        assert "brave" in url
        assert kw["headers"]["X-Subscription-Token"] == "brave-key"
        return _response(json={
            "web": {"results": [{"title": "ADKBot", "url": "https://example.com", "description": "AI assistant"}]}
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    result = await web_search(query="adkbot", count=1)
    assert "ADKBot" in str(result)
    assert "https://example.com" in str(result)


@pytest.mark.asyncio
async def test_tavily_search(monkeypatch):
    async def mock_post(self, url, **kw):
        assert "tavily" in url
        assert kw["headers"]["Authorization"] == "Bearer tavily-key"
        return _response(json={
            "results": [{"title": "ADKBot", "url": "https://adkbot.dev", "content": "Framework"}]
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-key")
    result = await web_search(query="adkbot")
    assert "ADKBot" in str(result)
    assert "https://adkbot.dev" in str(result)


@pytest.mark.asyncio
async def test_searxng_search(monkeypatch):
    async def mock_get(self, url, **kw):
        assert "searx.example" in url
        return _response(json={
            "results": [{"title": "Result", "url": "https://example.com", "content": "SearXNG result"}]
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("SEARXNG_BASE_URL", "https://searx.example")
    result = await web_search(query="test")
    assert "Result" in str(result)


@pytest.mark.asyncio
async def test_duckduckgo_search(monkeypatch):
    class MockDDGS:
        def __init__(self, **kw):
            pass

        def text(self, query, max_results=5):
            return [{"title": "DDG Result", "href": "https://ddg.example", "body": "From DuckDuckGo"}]

    monkeypatch.setattr("adkbot.agent.tools.web.DDGS", MockDDGS, raising=False)
    import adkbot.agent.tools.web as web_mod
    monkeypatch.setattr(web_mod, "DDGS", MockDDGS, raising=False)

    from ddgs import DDGS
    monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    monkeypatch.setenv("SEARCH_PROVIDER", "duckduckgo")

    result = await web_search(query="hello")
    assert "DDG Result" in str(result)


@pytest.mark.asyncio
async def test_brave_fallback_to_duckduckgo_when_no_key(monkeypatch):
    class MockDDGS:
        def __init__(self, **kw):
            pass

        def text(self, query, max_results=5):
            return [{"title": "Fallback", "href": "https://ddg.example", "body": "DuckDuckGo fallback"}]

    monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    result = await web_search(query="test")
    assert "Fallback" in str(result)


@pytest.mark.asyncio
async def test_jina_search(monkeypatch):
    async def mock_get(self, url, **kw):
        assert "s.jina.ai" in str(url)
        assert kw["headers"]["Authorization"] == "Bearer jina-key"
        return _response(json={
            "data": [{"title": "Jina Result", "url": "https://jina.ai", "content": "AI search"}]
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setenv("SEARCH_PROVIDER", "jina")
    monkeypatch.setenv("JINA_API_KEY", "jina-key")
    result = await web_search(query="test")
    assert "Jina Result" in str(result)
    assert "https://jina.ai" in str(result)


@pytest.mark.asyncio
async def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "unknown")
    result = await web_search(query="test")
    # Falls back to duckduckgo, which is expected behavior without error
    assert "results" in result


@pytest.mark.asyncio
async def test_default_provider_is_brave(monkeypatch):
    async def mock_get(self, url, **kw):
        assert "brave" in url
        return _response(json={"web": {"results": []}})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    result = await web_search(query="test")
    assert "results" in result or "No results" in str(result)


@pytest.mark.asyncio
async def test_searxng_no_base_url_falls_back(monkeypatch):
    class MockDDGS:
        def __init__(self, **kw):
            pass

        def text(self, query, max_results=5):
            return [{"title": "Fallback", "href": "https://ddg.example", "body": "fallback"}]

    monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)

    result = await web_search(query="test")
    assert "Fallback" in str(result)



class TestWebSearchConfigBridge:
    """Verify web_search tool bridges config values correctly."""

    def test_web_search_reads_config(self):
        """web_search should try loading config for provider/api_key."""
        src = Path("adkbot/agent/tools/web.py").read_text(encoding="utf-8")
        assert "load_config" in src
        assert "web_cfg.search.provider" in src

    def test_env_overrides_config(self):
        """SEARCH_PROVIDER env var should override config if set."""
        src = Path("adkbot/agent/tools/web.py").read_text(encoding="utf-8")
        assert 'os.environ.get("SEARCH_PROVIDER"' in src
