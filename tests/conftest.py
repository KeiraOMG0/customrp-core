import os
import shutil
import sys
import tempfile
import uuid

import pytest

from customrp_core.testing import FakeDiscord


@pytest.fixture
def ipc_dir():
    """A short directory for Unix sockets (their paths are limited to about 100 characters)."""
    path = tempfile.mkdtemp(prefix="crp-", dir=None if sys.platform == "win32" else "/tmp")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def fake_address(ipc_dir):
    """An endpoint address that can't clash with a real Discord client."""
    if sys.platform == "win32":
        return rf"\\.\pipe\customrp-core-test-{uuid.uuid4().hex}"
    return os.path.join(ipc_dir, "fake-discord")


@pytest.fixture
def discord(fake_address):
    with FakeDiscord(fake_address) as server:
        yield server
