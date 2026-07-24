"""Shared pytest fixtures for the BookGPT test suite."""
import os
import sys
import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from utils.database import BookDatabase
from models.book_model import BookProject


# ---------------------------------------------------------------------------
# Unit-test fixtures (no Flask, no network)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """A BookDatabase backed by a temp SQLite file (hermetic)."""
    db = BookDatabase(str(tmp_path / "bookgpt.db"))
    yield db
    # Best-effort cleanup; ignore Windows file locks from WAL sidecar files.
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / f"bookgpt.db{suffix}"
        try:
            if p.exists():
                os.remove(p)
        except OSError:
            pass


@pytest.fixture
def make_project():
    """Factory for BookProject instances with sensible defaults."""
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        defaults = dict(
            id=f"proj-{counter['n']}",
            user_id="user-1",
            title="Test Book",
            genre="fantasy",
            target_length=10000,
            writing_style="modern",
        )
        defaults.update(overrides)
        return BookProject(**defaults)

    return _make


@pytest.fixture
def isolated_projects_dir(tmp_path, monkeypatch):
    """Redirect PROJECTS_BASE_DIR to a temp dir so file tools never touch the repo."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    import tools.file_tools as ft
    monkeypatch.setattr(ft, "PROJECTS_BASE_DIR", str(projects_dir))
    return projects_dir


@pytest.fixture
def mock_llm():
    """A fake LLM client whose .chat returns configurable content."""
    llm = MagicMock()
    llm.chat.return_value = SimpleNamespace(content="chapter body " * 200, usage=None)
    return llm


@pytest.fixture
def agent(tmp_db, mock_llm, isolated_projects_dir):
    """A BookWritingAgent with real file tools, a mock LLM, and isolated project dirs."""
    from utils.agent_factory import ALL_TOOLS
    from book_agent import BookWritingAgent
    # Fresh tool instances so no state leaks between tests.
    tools = [
        type(t)() for t in ALL_TOOLS.values()
    ]
    a = BookWritingAgent(tools=tools, llm_client=mock_llm, db=tmp_db)
    return a


# ---------------------------------------------------------------------------
# Flask app fixture (module-level app import is isolated to a temp cwd +
# temp instance path so users.db / bookgpt.db never pollute the repo)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def flask_app(tmp_path_factory):
    import flask

    tmp = tmp_path_factory.mktemp("flaskapp")
    instance_dir = tmp / "instance"
    instance_dir.mkdir()

    # Configure the environment the way a test run should look.
    os.environ["FLASK_SECRET_KEY"] = "test-secret-key-not-the-default"
    os.environ["STRIPE_ENABLED"] = "false"
    os.environ.setdefault("UNLIMITED_USAGE", "true")

    # Force Flask's instance_path into the temp dir so the SQLAlchemy
    # `sqlite:///users.db` file lands in tmp, not in the repo's instance/.
    orig_flask = flask.Flask

    class _PatchedFlask(orig_flask):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("instance_path", str(instance_dir))
            super().__init__(*args, **kwargs)

    flask.Flask = _PatchedFlask

    prev_cwd = os.getcwd()
    os.chdir(tmp)  # so cwd-relative `data/bookgpt.db` lands in tmp
    sys.path.insert(0, str(tmp))  # not strictly needed, but keeps imports happy

    # Drop any cached import so the patching takes effect.
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")

    # Restore Flask for any other consumers.
    flask.Flask = orig_flask

    yield app_module

    os.chdir(prev_cwd)


@pytest.fixture
def client(flask_app):
    """A Flask test client with an application context."""
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        with flask_app.app.app_context():
            yield c