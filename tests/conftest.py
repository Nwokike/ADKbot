import sys
import asyncio
import gc
import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def _windows_proactor_cleanup():
    """Allow Windows Proactor to fully process transport closure callbacks."""
    yield
    if sys.platform == "win32":
        gc.collect()
        await asyncio.sleep(0.1)
