"""BookWritingAgent correctness fixes.

Covers:
- per-project progress callbacks (no cross-project clobbering)
- _report_progress / set_progress_callback / clear_progress_callback signatures
- _run_agentic_loop accepts resume=True (was a TypeError before the fix)
- the writing loop is decoupled from max_iterations (a long book is not cut short)
- conversation_history is trimmed on save (unbounded growth fixed)
- _read_previous_chapter reads the prior chapter for cross-chapter continuity
"""
import inspect
from unittest.mock import MagicMock

import pytest

from book_agent import BookWritingAgent


# ---------------------------------------------------------------------------
# Per-project progress callbacks
# ---------------------------------------------------------------------------

class TestProgressCallbacks:
    def test_set_and_report_invokes_callback(self, agent):
        calls = []
        agent.set_progress_callback("p1", lambda *a: calls.append(a))
        agent._report_progress("p1", "writing", 50.0, "msg", "act")
        assert len(calls) == 1
        assert calls[0][0] == "writing"
        assert calls[0][1] == 50.0

    def test_callbacks_are_isolated_per_project(self, agent):
        a, b = [], []
        agent.set_progress_callback("pa", lambda *args: a.append(args))
        agent.set_progress_callback("pb", lambda *args: b.append(args))

        agent._report_progress("pa", "writing", 1.0, "x", "y")
        assert len(a) == 1 and b == []

        agent._report_progress("pb", "writing", 2.0, "x", "y")
        assert len(b) == 1 and len(a) == 1

    def test_clear_progress_callback_stops_calls(self, agent):
        calls = []
        agent.set_progress_callback("p1", lambda *args: calls.append(args))
        agent.clear_progress_callback("p1")
        agent._report_progress("p1", "writing", 1.0, "x", "y")
        assert calls == []

    def test_report_progress_swallows_callback_errors(self, agent):
        def boom(*args):
            raise RuntimeError("callback exploded")
        agent.set_progress_callback("p1", boom)
        # must not raise
        agent._report_progress("p1", "writing", 1.0, "x", "y")

    def test_report_progress_with_no_callback_is_noop(self, agent):
        agent._report_progress("never-registered", "writing", 1.0, "x", "y")


# ---------------------------------------------------------------------------
# Resume signature (the TypeError fix)
# ---------------------------------------------------------------------------

class TestResumeSignature:
    def test_run_agentic_loop_has_resume_parameter(self):
        sig = inspect.signature(BookWritingAgent._run_agentic_loop)
        assert "resume" in sig.parameters
        assert sig.parameters["resume"].default is False

    def test_run_agentic_loop_accepts_resume_true_without_typeerror(self, agent, make_project):
        # 'refining' phase has no handler in _run_agentic_loop, so it returns
        # success immediately without any LLM calls — exercising the signature.
        project = make_project(status="refining")
        agent.project_states[project.id] = {
            "project": project,
            "current_phase": "refining",
            "chapter_count": 0,
            "total_words": 0,
            "iterations": 0,
            "completed": False,
            "errors": [],
            "conversation_history": [],
        }
        result = agent._run_agentic_loop(project.id, resume=True)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Writing loop decoupling from max_iterations
# ---------------------------------------------------------------------------

class TestWritingLoopDecoupling:
    def test_writes_all_chapters_despite_low_max_iterations(self, agent, make_project, monkeypatch):
        # target_length=10000 -> target_chapters = 10000//5000 = 2.
        # Set max_iterations=1; the OLD loop `while writing and iters<max_iter`
        # would stop after 1 chapter. The fixed loop must write both.
        project = make_project(target_length=10000, status="writing")
        agent.max_iterations = 1
        agent.project_states[project.id] = {
            "project": project,
            "current_phase": "writing",
            "chapter_count": 0,
            "total_words": 0,
            "iterations": 0,
            "completed": False,
            "errors": [],
            "conversation_history": [],
            "outline": {"chapters": [{"summary": "s1"}, {"summary": "s2"}], "raw_content": "outline"},
            "research_materials": {"raw_content": "research"},
        }
        # Skip the editing phase (needs a richer LLM mock) — just record it ran.
        monkeypatch.setattr(
            agent, "_execute_editing_phase",
            lambda pid: {"success": True, "changes": []},
        )

        result = agent._run_agentic_loop(project.id, resume=True)

        assert result["success"] is True
        assert result["chapters_completed"] >= 2, "loop stopped early like the old max_iterations bug"
        # max_iterations was 1 yet 2 chapters were written -> decoupled.
        assert agent.project_states[project.id]["iterations"] >= 2


# ---------------------------------------------------------------------------
# Conversation history trimming
# ---------------------------------------------------------------------------

class TestConversationHistoryTrim:
    def test_save_trims_overlong_history(self, agent, make_project, tmp_db):
        project = make_project()
        # Persist the project first so save has a row to update.
        tmp_db.save_project(project)
        agent.project_states[project.id] = {
            "project": project,
            "current_phase": "writing",
            "chapter_count": 0,
            "total_words": 0,
            "iterations": 0,
            "completed": False,
            "errors": [],
            "conversation_history": [{"role": "user", "content": f"m{i}"} for i in range(200)],
        }
        agent._save_project_state(project.id)

        reloaded = tmp_db.get_project(project.id)
        history = reloaded.metadata.get("conversation_history", [])
        assert len(history) <= 100
        # Most recent are retained.
        assert history[-1]["content"] == "m199"

    def test_save_keeps_short_history_intact(self, agent, make_project, tmp_db):
        project = make_project()
        tmp_db.save_project(project)
        short = [{"role": "user", "content": f"m{i}"} for i in range(5)]
        agent.project_states[project.id] = {
            "project": project,
            "current_phase": "writing",
            "chapter_count": 0,
            "total_words": 0,
            "iterations": 0,
            "completed": False,
            "errors": [],
            "conversation_history": list(short),
        }
        agent._save_project_state(project.id)
        reloaded = tmp_db.get_project(project.id)
        assert len(reloaded.metadata["conversation_history"]) == 5


# ---------------------------------------------------------------------------
# Cross-chapter context
# ---------------------------------------------------------------------------

class TestReadPreviousChapter:
    def test_reads_written_chapter(self, agent, make_project, isolated_projects_dir):
        project = make_project()
        content = "The hero stood at the gates.\n\nTHE END."
        # Write chapter 1 to the project dir via the real write_file tool.
        agent.tools["write_file"].execute(
            project_id=project.id, path="chapters/chapter_1.md", content=content
        )
        result = agent._read_previous_chapter(project.id, 1)
        assert result is not None
        assert "hero stood" in result

    def test_returns_none_for_missing_chapter(self, agent, make_project):
        project = make_project()
        assert agent._read_previous_chapter(project.id, 99) is None