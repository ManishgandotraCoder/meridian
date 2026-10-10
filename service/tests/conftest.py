from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meridian.api import create_app
from meridian.directory import load_directory
from meridian.ingest import build_facts

ROOT = Path(__file__).resolve().parents[2]

PRIYA = "user_E7691888F28227066DD2FB86"
DANIEL = "user_699C48763F6FA2958D2CDB5D"
MEI = "user_B3DEF4602E6A0912588C6D50"
CHLOE = "user_533B58E6F66C98ACB833527A"


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def directory(root):
    return load_directory(root / "starter-kit" / "data" / "directory")


@pytest.fixture(scope="session")
def facts(root, directory):
    return build_facts(root / "starter-kit" / "data", directory)


@pytest.fixture
def client(tmp_path):
    def _make(env="prod", db_name="meridian.db"):
        app = create_app(ROOT, env, tmp_path / db_name)
        return TestClient(app)

    return _make
