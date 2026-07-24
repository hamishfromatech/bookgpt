"""SQLite persistence: WAL pragmas, project round-trip, comment CRUD.

Comments were previously stored in an in-memory dict on the Flask app and lost
on every restart. They now persist to a `comments` table. This also verifies
the WAL/busy_timeout pragmas that prevent 'database is locked' under the
threaded task manager.
"""
import sqlite3

from models.book_model import BookProject


class TestDatabasePragmas:
    def test_wal_journal_mode_is_enabled(self, tmp_db, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "bookgpt.db"))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode.lower() == "wal"

    def test_busy_timeout_is_set(self, tmp_db):
        # _connect applies busy_timeout; verify via a fresh managed connection.
        conn = tmp_db._connect()
        bt = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()
        assert bt >= 30000


class TestProjectRoundTrip:
    def test_save_and_get_project(self, tmp_db, make_project):
        project = make_project(title="Round Trip")
        assert tmp_db.save_project(project) is True

        loaded = tmp_db.get_project(project.id)
        assert loaded is not None
        assert loaded.title == "Round Trip"
        assert loaded.user_id == project.user_id

    def test_get_nonexistent_project_returns_none(self, tmp_db):
        assert tmp_db.get_project("does-not-exist") is None


class TestCommentPersistence:
    def _comment(self, project_id="p1", cid="c1", user_id="u1"):
        return {
            "id": cid,
            "project_id": project_id,
            "user_id": user_id,
            "user_username": "alice",
            "comment": "fix this line",
            "chapter_number": 1,
            "line_number": 10,
        }

    def test_add_and_get_comments(self, tmp_db):
        tmp_db.add_comment(self._comment(cid="c1"))
        tmp_db.add_comment(self._comment(cid="c2", user_id="u2"))
        comments = tmp_db.get_comments("p1")
        assert len(comments) == 2
        ids = {c["id"] for c in comments}
        assert ids == {"c1", "c2"}
        # default unresolved
        assert all(c["resolved"] is False for c in comments)

    def test_comments_are_scoped_to_project(self, tmp_db):
        tmp_db.add_comment(self._comment(project_id="p1", cid="c1"))
        tmp_db.add_comment(self._comment(project_id="p2", cid="c2"))
        assert len(tmp_db.get_comments("p1")) == 1
        assert len(tmp_db.get_comments("p2")) == 1

    def test_get_single_comment(self, tmp_db):
        tmp_db.add_comment(self._comment(cid="c9"))
        c = tmp_db.get_comment("c9")
        assert c is not None
        assert c["comment"] == "fix this line"

    def test_resolve_comment(self, tmp_db):
        tmp_db.add_comment(self._comment(cid="c1"))
        updated = tmp_db.resolve_comment("c1", resolved_by="u2")
        assert updated is not None
        assert updated["resolved"] is True
        assert updated["resolved_by"] == "u2"

    def test_delete_comment(self, tmp_db):
        tmp_db.add_comment(self._comment(cid="c1"))
        assert tmp_db.delete_comment("c1") is True
        assert tmp_db.get_comment("c1") is None

    def test_comments_survive_reopen(self, tmp_db, tmp_path):
        # The whole point of the fix: comments must survive a new BookDatabase
        # instance pointed at the same file (simulates a server restart).
        from utils.database import BookDatabase as _DB
        tmp_db.add_comment(self._comment(cid="c1"))
        tmp_db.add_comment(self._comment(cid="c2"))

        reopened = _DB(str(tmp_path / "bookgpt.db"))
        comments = reopened.get_comments("p1")
        assert len(comments) == 2