"""Path containment for the file tools.

`resolve_path` must reject `../` escapes and string-prefix confusion between
project ids (e.g. projects/abc vs projects/abcdef). The previous
`startswith` implementation accepted both of those as "inside" the project.
"""
import os
import pytest

from tools.file_tools import resolve_path


class TestResolvePathContainment:
    def test_valid_relative_path_is_accepted(self, isolated_projects_dir):
        full = resolve_path("abc-123", "chapters/chapter_1.md")
        assert full == os.path.normpath(str(isolated_projects_dir / "abc-123" / "chapters/chapter_1.md"))

    def test_root_path_is_accepted(self, isolated_projects_dir):
        full = resolve_path("abc-123", "outline.md")
        assert full.endswith(os.path.join("abc-123", "outline.md"))

    def test_parent_traversal_is_rejected(self, isolated_projects_dir):
        with pytest.raises(ValueError):
            resolve_path("abc-123", "../../etc/passwd")

    def test_dotdot_inside_path_is_rejected(self, isolated_projects_dir):
        with pytest.raises(ValueError):
            resolve_path("abc-123", "chapters/../../secret.md")

    def test_absolute_path_outside_is_rejected(self, isolated_projects_dir, tmp_path):
        outside = tmp_path / "outside.txt"
        with pytest.raises(ValueError):
            resolve_path("abc-123", str(outside))

    def test_prefix_confusion_between_project_ids_is_rejected(self, isolated_projects_dir):
        # A naive startswith(base_path) check would treat projects/abcdef as
        # inside projects/abc. commonpath must reject this.
        with pytest.raises(ValueError):
            resolve_path("abc", "../abc-def/secret.md")

    def test_null_byte_does_not_bypass_check(self, isolated_projects_dir):
        # normpath/cleanpath should not let a null byte smuggle an escape.
        with pytest.raises((ValueError, Exception)):
            resolve_path("abc-123", "ok\x00/../../etc/passwd")