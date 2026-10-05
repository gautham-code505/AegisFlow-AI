import inspect
import asyncio
import asyncio.coroutines
import sys

# Aggressively patch asyncio.iscoroutinefunction to bypass Python 3.14 deprecation
# This is done here at the module level of conftest.py so it runs right before
# test collection, after pytest has loaded its own internals, ensuring the patch sticks.
asyncio.iscoroutinefunction = inspect.iscoroutinefunction
asyncio.coroutines.iscoroutinefunction = inspect.iscoroutinefunction
sys.modules['asyncio'].iscoroutinefunction = inspect.iscoroutinefunction
if 'asyncio.coroutines' in sys.modules:
    sys.modules['asyncio.coroutines'].iscoroutinefunction = inspect.iscoroutinefunction

import pytest
@pytest.fixture(params=["asyncio"])
def anyio_backend():
    return "asyncio"

