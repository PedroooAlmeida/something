import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="gordon-test-")
os.environ["GORDON_DB"] = os.path.join(_tmp, "test.db")
os.environ["GORDON_SCREENSHOTS"] = os.path.join(_tmp, "screenshots")
os.environ.pop("GORDON_ENGINE_URL", None)  # tests always use the mock evaluator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:  # context manager runs startup (db init + seed)
        c.delete("/api/history")
        c.post("/api/monitoring/resume")
        yield c
