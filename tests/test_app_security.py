"""End-to-end security behaviors via the Flask test client.

Covers the app.py fixes:
- session SECRET_KEY is never the hardcoded public default
- @login_required on /api/llm/config (and other) API routes
- forced-password-change gate returns 403 for API/JSON clients
- project/comment ownership checks (IDOR): user B cannot read user A's project
"""
import uuid

import pytest


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestSecretKey:
    def test_secret_key_is_set_and_not_the_default(self, flask_app):
        key = flask_app.app.config.get("SECRET_KEY")
        assert key
        assert key != "dev-secret-key-12345"
        # We seeded FLASK_SECRET_KEY in the fixture; confirm it was honored.
        assert key == "test-secret-key-not-the-default"


class TestAuthenticationGate:
    def test_unauthenticated_api_redirects_to_login(self, client):
        r = client.get("/api/llm/config", headers={"Accept": "application/json"})
        # Not authenticated -> login_required fires (before the password gate
        # passes an anonymous user through). Browser clients get a 302 to
        # /login; JSON clients may also get 302 since login_required redirects.
        assert r.status_code in (301, 302, 401, 403)
        assert r.status_code != 200

    def test_login_page_is_reachable(self, client):
        r = client.get("/login")
        assert r.status_code == 200


class TestForcedPasswordChange:
    def test_default_user_is_flagged_must_change(self, flask_app):
        with flask_app.app.app_context():
            from app import User
            user = User.query.filter_by(username="user").first()
            assert user is not None
            assert user.must_change_password is True

    def test_api_blocked_while_password_change_required(self, client):
        # The seeded 'user'/'password' account has must_change_password=True.
        r = client.post("/login", data={"username": "user", "password": "password"})
        assert r.status_code == 302  # redirected to /change-password

        # Authenticated but flagged: API/JSON request must be refused with 403.
        r = client.get("/api/llm/config", headers={"Accept": "application/json"})
        assert r.status_code == 403
        assert r.get_json()["error"] == "Password change required"

    def test_changing_password_unblocks_api(self, client):
        client.post("/login", data={"username": "user", "password": "password"})
        # Change the password to clear the flag.
        r = client.post("/change-password", data={"password": "newpass-123"})
        assert r.status_code == 302  # redirect to index

        # API should now be reachable (login_required passes).
        r = client.get("/api/llm/config", headers={"Accept": "application/json"})
        assert r.status_code == 200
        assert r.get_json()["success"] is True


class TestProjectOwnership:
    """IDOR guard: a second user must not access another user's project."""

    def test_other_user_cannot_read_comments(self, client):
        # User A registers (new users are NOT flagged must_change_password).
        user_a = _unique("alice")
        client.post("/register", data={"username": user_a, "email": f"{user_a}@x.test", "password": "pw-a-123"})
        # Create a project as user A.
        r = client.post(
            "/api/projects",
            json={"title": "A's book", "genre": "fantasy", "target_length": 10000, "writing_style": "modern"},
        )
        assert r.status_code == 200
        project_id = r.get_json()["project"]["id"]

        # Log out and register user B.
        client.get("/logout")
        user_b = _unique("bob")
        client.post("/register", data={"username": user_b, "email": f"{user_b}@x.test", "password": "pw-b-123"})

        # User B must be denied access to user A's project comments.
        r = client.get(f"/api/projects/{project_id}/comments", headers={"Accept": "application/json"})
        assert r.status_code == 403

    def test_owner_can_read_own_comments(self, client):
        user = _unique("carol")
        client.post("/register", data={"username": user, "email": f"{user}@x.test", "password": "pw-c-123"})
        r = client.post(
            "/api/projects",
            json={"title": "Carol's book", "genre": "fantasy", "target_length": 10000, "writing_style": "modern"},
        )
        project_id = r.get_json()["project"]["id"]
        r = client.get(f"/api/projects/{project_id}/comments", headers={"Accept": "application/json"})
        assert r.status_code == 200
        assert r.get_json()["success"] is True