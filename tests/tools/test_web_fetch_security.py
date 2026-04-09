"""Tests for web_fetch SSRF protection and untrusted content marking."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from adkbot.agent.tools.web import web_fetch


def _fake_resolve_private(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))]


def _fake_resolve_public(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_ip():
    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_private):
        result = await web_fetch(url="http://169.254.169.254/computeMetadata/v1/")
    assert "error" in result
    assert "private" in result["error"].lower() or "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_web_fetch_blocks_localhost():
    def _resolve_localhost(hostname, port, family=0, type_=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]
    with patch("adkbot.security.network.socket.getaddrinfo", _resolve_localhost):
        result = await web_fetch(url="http://localhost/admin")
    assert "error" in result


@pytest.mark.asyncio
async def test_web_fetch_result_contains_untrusted_flag():
    """When fetch succeeds, result JSON must include untrusted=True and the banner."""
    fake_html = "<html><head><title>Test</title></head><body><p>Hello world</p></body></html>"

    import httpx

    class FakeResponse:
        status_code = 200
        url = "https://example.com/page"
        text = fake_html
        headers = {"content-type": "text/html"}
        def raise_for_status(self): pass
        def json(self): return {}

    async def _fake_get(self, url, **kwargs):
        return FakeResponse()

    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_public), \
         patch("httpx.AsyncClient.get", _fake_get):
        result = await web_fetch(url="https://example.com/page")

    assert result.get("untrusted") is True
    assert "[External content" in result.get("text", "")


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_redirect_before_returning_image(monkeypatch):
    class FakeStreamResponse:
        headers = {"content-type": "image/png"}
        url = "http://127.0.0.1/secret.png"
        content = b"\x89PNG\r\n\x1a\n"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aread(self):
            return self.content

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None):
            return FakeStreamResponse()

    monkeypatch.setattr("adkbot.agent.tools.web.httpx.AsyncClient", FakeClient)

    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_public):
        result = await web_fetch(url="https://example.com/image.png")

    assert "error" in result
    assert "redirect blocked" in result["error"].lower()
