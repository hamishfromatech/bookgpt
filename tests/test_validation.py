"""Input validation utilities.

These tests also lock in the fix for the `validate_request` decorator, which
previously used `request.get_json()` and `jsonify(...)` without importing them
from Flask — raising NameError whenever the decorator was actually applied.
"""
import pytest
from flask import Flask

from utils.validation import (
    ValidationError,
    validate_string,
    validate_integer,
    validate_email,
    validate_project_title,
    validate_file_path,
    validate_uuid,
    validate_request,
)


class TestPrimitives:
    def test_validate_string_strips_and_checks_length(self):
        assert validate_string("  hi  ", "f", min_length=1, max_length=10) == "hi"

    def test_validate_string_rejects_too_long(self):
        with pytest.raises(ValidationError):
            validate_string("x" * 20, "f", max_length=5)

    def test_validate_string_rejects_non_string(self):
        with pytest.raises(ValidationError):
            validate_string(123, "f")

    def test_validate_integer_clamps_range(self):
        assert validate_integer(5, "n", min_value=1, max_value=10) == 5
        with pytest.raises(ValidationError):
            validate_integer(0, "n", min_value=1)
        with pytest.raises(ValidationError):
            validate_integer(11, "n", max_value=10)

    def test_validate_email_accepts_valid(self):
        assert validate_email("User@Example.COM") == "user@example.com"

    def test_validate_email_rejects_garbage(self):
        with pytest.raises(ValidationError):
            validate_email("not-an-email")

    def test_validate_uuid_accepts_valid(self):
        u = "12345678-1234-1234-1234-1234567890ab"
        assert validate_uuid(u) == u

    def test_validate_uuid_rejects_garbage(self):
        with pytest.raises(ValidationError):
            validate_uuid("not-a-uuid")


class TestFilePathValidation:
    def test_rejects_parent_traversal(self):
        with pytest.raises(ValidationError):
            validate_file_path("../../etc/passwd")

    def test_rejects_null_bytes(self):
        # null byte stripped, then validated
        result = validate_file_path("ok\x00file.md")
        assert "\x00" not in result

    def test_strips_leading_slash(self):
        assert validate_file_path("/chapters/one.md") == "chapters/one.md"


class TestValidateRequestDecorator:
    """The decorator used to NameError because `request`/`jsonify` were not imported."""

    def _make_app(self):
        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/echo", methods=["POST"])
        @validate_request(lambda d: validate_project_title(d.get("title")))
        def echo():
            return jsonify_ok()

        def jsonify_ok():
            from flask import jsonify
            return jsonify({"ok": True})

        return app

    def test_decorator_returns_400_on_invalid_body(self):
        app = self._make_app()
        with app.test_client() as c:
            r = c.post("/echo", json={"title": ""})
            assert r.status_code == 400
            data = r.get_json()
            assert data["success"] is False

    def test_decorator_passes_valid_body_through(self):
        app = self._make_app()
        with app.test_client() as c:
            r = c.post("/echo", json={"title": "A Real Title"})
            assert r.status_code == 200
            assert r.get_json()["ok"] is True

    def test_decorator_does_not_raise_nameerror(self):
        # The historical bug: applying/invoking the decorator raised NameError
        # at request time. Ensure it no longer does for a missing field.
        app = self._make_app()
        with app.test_client() as c:
            r = c.post("/echo", json={})  # title missing -> validation error, not NameError
            assert r.status_code == 400
            assert "errors" in r.get_json()