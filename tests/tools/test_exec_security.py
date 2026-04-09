"""Tests for exec tool internal URL blocking."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from adkbot.agent.tools.shell import execute_command


def _fake_resolve_private(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))]


def _fake_resolve_localhost(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]


def _fake_resolve_public(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


@pytest.mark.asyncio
async def test_exec_blocks_curl_metadata():
    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_private):
        result = await execute_command(
            command='curl -s -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/'
        )
    assert "error" in result
    assert "internal" in result["error"].lower() or "private" in result["error"].lower()


@pytest.mark.asyncio
async def test_exec_blocks_wget_localhost():
    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_localhost):
        result = await execute_command(command="wget http://localhost:8080/secret -O /tmp/out")
    assert "error" in result


@pytest.mark.asyncio
async def test_exec_allows_normal_commands():
    result = await execute_command(command="echo hello", timeout=5)
    assert "hello" in str(result)
    assert "error" not in result


@pytest.mark.asyncio
async def test_exec_allows_curl_to_public_url():
    """Commands with public URLs should not be blocked by the internal URL check."""
    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_public):
        result = await execute_command(command="curl https://example.com/api")
    # if it fails, it shouldn't be for security reasons
    assert "error" not in result or "blocked" not in result["error"].lower()


@pytest.mark.asyncio
async def test_exec_blocks_chained_internal_url():
    """Internal URLs buried in chained commands should still be caught."""
    with patch("adkbot.security.network.socket.getaddrinfo", _fake_resolve_private):
        result = await execute_command(
            command="echo start && curl http://169.254.169.254/latest/meta-data/ && echo done"
        )
    assert "error" in result
