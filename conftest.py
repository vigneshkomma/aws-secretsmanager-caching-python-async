import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit test marker")
    config.addinivalue_line("markers", "local: Local test marker")
    # Suppress deprecation by setting default loop scope for async fixtures
    config.known_args_namespace.asyncio_default_fixture_loop_scope = "function"