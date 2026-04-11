"""Tests for the message bus queue logic."""

from __future__ import annotations

import asyncio
from adkbot.bus.queue import MessageBus

class TestQueueBackpressure:
    """Verify queues have maxsize for backpressure support."""

    def test_queue_has_maxsize_param(self):
        """MessageBus constructor should accept maxsize."""
        bus = MessageBus(maxsize=10)
        assert bus.inbound.maxsize == 10
        assert bus.outbound.maxsize == 10

    def test_default_maxsize(self):
        """Default maxsize should be 1000."""
        bus = MessageBus()
        assert bus.inbound.maxsize == 1000
