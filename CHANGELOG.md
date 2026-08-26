# Changelog

All notable changes to BookGPT are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Upcoming
- Vector-based RAG for chapter context using Ollama embeddings
- Character bible & world wiki with persistent memory
- Scene-level writing (break chapters into scenes for richer detail)
- Human-in-the-loop approval gates between phases
- Show-don't-tell detection in editing passes

---

## [2026-08-26] — Writing Quality Engine

### Added
- **Multi-Draft Writing Process** (`writing_quality.py`): Four progressive passes—rough draft, structural edit, line edit, and proofread—each with distinct system prompts and temperature settings. Users can select 1-4 passes per project.
- **Self-Critique Loop**: Agent reads its own chapter, scores it against a 7-criterion rubric (pacing, dialogue, sensory detail, conflict, character voice, show-don't-tell, scene structure), identifies the 3 weakest sections with specific suggestions, and rewrites the chapter accordingly.
- **Style Transfer & Author Mimicry**: Eight distinct author voices (Literary, Hemingway/Minimalist, Thriller, Romance, Sci-Fi, Fantasy Epic, Technical, Poetic), each with tailored system prompts and few-shot prose examples injected into writing prompts.
- **Structural Templates**: Five beat sheets mapped to chapter positions—Save the Cat (15 beats), Hero's Journey (12 stages), Three-Act (9 beats), Seven-Point (7 beats), and Freytag's Pyramid (5 parts). Each chapter receives guidance about which beat it should fulfill.
- **Advanced Quality Options UI**: Collapsible section in the New Manuscript modal with Structure Template dropdown, Writing Voice dropdown, Draft Passes selector (1-4), and Self-Critique Loop checkbox.
- `BookProject` model extended with `structure_template`, `style_voice`, `draft_passes`, and `self_critique` fields (with full serialization).

### Changed
- Writing phase now runs multi-draft passes and self-critique loop after the rough draft, before saving the chapter.
- Planning and writing phase system prompts include skill, style, and structure guidance via unified `_get_skill_guidance`.
- Per-chapter beat guidance injected from the selected structure template.
- All draft passes and critique cycles logged in the agent activity log.
- Create project API accepts all new quality parameters; form submission handles checkbox and number conversion.

---

## [2026-08-20] — Skills System, Agentic Experience, Multi-Agent, Analytics & Visualization

### Added

#### Skills System
- **Domain-specific writing skills** following the Agent Skills Specification with progressive disclosure pattern:
  - `fiction-writer`: Novel and fiction writing with character arcs, plot beats, dialogue focus
  - `non-fiction-author`: Research citation, factual accuracy, logical structure
  - `academic-writer`: Formal tone, peer-review style, reference formatting, methodological rigor
  - `childrens-book-creator`: Simple language, educational themes, illustration prompts
  - `screenplay-writer`: Scene headings, action lines, dialogue formatting, visual storytelling
- Skill selection dropdown in the project creation modal.
- `BookProject` model extended with `skill` field.

#### Agentic Experience Improvements
- **Running Summary Tool**: Maintains story context across chapters with character introductions and location tracking.
- **Agent Activity Logging**: `AgentActivityLog` class captures phase actions, tool calls, results, and reasoning; persisted to project metadata.
- **Cross-Chapter Consistency Checks**: Uses `grep_search` before editing to verify character names and locations across all chapters.
- **Adaptive Retry Strategies**: Up to 3 retry attempts with reduced token limits and simplified fallback prompts for failed chapter generation.
- **Partial Chapter Recovery**: Detects truncated responses and retries automatically.
- **Proactive Suggestions**: Generates context-aware recommendations based on project state (editing, consistency, export, outline review).
- **Writing-specific tools** (`tools/writing_tools.py`): `RunningSummaryTool`, `ChapterEvaluationTool`, `CharacterConsistencyTool`.

#### Multi-Agent Architecture (`agent_architecture.py`)
- **Specialized sub-agents** using the `SupervisorMode` pattern: planning agent, writing agent, editing agent, consistency agent.
- **BookSupervisor** class coordinates delegation to specialists based on task requirements.

#### Analytics Dashboard
- **Pacing Analysis**: Chapter length tracking with min/max/average insights (`/api/projects/<id>/analytics/pacing`).
- **Character Frequency Tracking**: Analyzes introduced characters across chapters (`/api/projects/<id>/analytics/characters`).
- **Readability Scoring**: Flesch-Kincaid Grade Level approximation for target audience alignment (`/api/projects/<id>/analytics/readability`).

#### Multilingual Support
- Supported languages endpoint listing 9 languages (English, Spanish, French, German, Italian, Portuguese, Russian, Japanese, Chinese).
- Translation endpoint placeholder for future pipeline (`/api/projects/<id>/translate`).

#### Visualization
- **Story Arc Timeline**: Visual timeline showing 4 narrative phases (Setup, Rising Action, Climax, Resolution) with current phase highlighting (`/api/projects/<id>/story-arc`).
- **Chapter Version Diff View**: Visual unified diff between chapter versions with color-coded added/removed/modified lines (`/api/projects/<id>/chapters/<num>/diff`).
- `ChapterVersionDiff` model for tracking version changes.
- Story Arc Timeline modal and Version Diff View modal with CSS styles.
- "Story Arc Timeline" button in project details modal.

#### Platform Documentation
- **In-app Help & Best Practices page** (`templates/docs.html`) with sidebar navigation, phase-by-phase guides, proactive suggestions table, export format comparison, pro tips, and troubleshooting.
- **Best practices guide** (`docs/best-practices.md`) with comprehensive usage documentation.
- "Help & Docs" sidebar link in `base.html`.
- `/docs` route in `app.py`.

#### UI/UX Enhancements
- Proactive suggestions panel in chat drawer with clickable cards.
- Expanded chat drawer width (32rem → 38rem).
- Agent activity feed with color-coded tool call cards.
- SSE streaming support for `suggestions` update type.

### Changed
- Updated README with skills system, agentic features, updated roadmap, project structure, and development guide.

### Fixed
- `SKILL_PROMPTS` dictionary missing closing brace.
- f-string syntax error in `_get_skill_guidance` method.
- HTML visualization string formatting in `generate_story_arc_visualization`.
- Misplaced route decorator and function definition in `app.py`.

---

## [2026-07-24] — Security & Correctness Hardening + Test Suite

### Added
- **Pytest test suite** (58 tests, `pytest.ini` + `tests/`) covering security, correctness, and robustness; hermetic via temp dirs and Flask instance-path patch.

### Fixed

#### Security (app.py)
- Persistent random session secret key instead of hardcoded default.
- Scoped CORS, `supports_credentials=False`.
- Forced-password-change gate (403 for API/JSON clients).
- `@login_required` + ownership checks on `/api/llm/config`, `/api/writing/config`, `/api/files/content`, `/api/projects/<id>/chat`, chapters/status, and comments.
- Path-traversal containment via `os.path.commonpath` on `/api/files/content`.
- Comments persisted to SQLite (were an in-memory dict lost on restart).
- `_verify_project_owner` fixed to return a 2-tuple (was returning 3, crashing callers with a 500 instead of a clean 403/404).

#### Correctness (book_agent.py)
- `_run_agentic_loop` accepts `resume=True` (was a TypeError, discarding progress).
- Writing loop decoupled from `max_iterations`, bounded by `max_chapters` cap.
- Cross-chapter continuity via `_read_previous_chapter`.
- Raised chapter `max_tokens` (4096 → 8000) to stop mid-chapter truncation.
- Per-project progress callbacks (thread-safe) replacing single shared callback.
- Trim `conversation_history` on save to prevent unbounded growth.
- Stopped polluting streaming chat history with "Thinking..." placeholders.

#### Robustness
- `llm_client`: guard `response.usage=None` (Ollama/LM Studio/vLLM) in `chat()` and `chat_with_tools()` via `_safe_usage()`.
- `file_tools.resolve_path`: commonpath containment (was startswith prefix-confusion).
- `database`: WAL + busy_timeout + foreign_keys per connection.
- `validation`: add missing flask import so `validate_request` no longer NameErrors.
- `task_manager`: per-project callback signature + progress tracking on resume.

---

## [2026-04-07] — User Ownership, Billing, Versioning & LLM Configuration

### Added
- **User ownership**: Projects scoped to authenticated users.
- **Rate limiting**: API protection with configurable limits.
- **Stripe billing control**: Credit-based system with subscription support; can be disabled for local usage.
- **Chapter versioning**: Track and restore previous chapter versions.
- **Resume functionality**: Stop and resume writing sessions anytime with state preservation.
- **User-configurable LLM settings**: Database-backed LLM configuration with fallback to `.env`.
- **Setup wizard skip logic**: Skips setup wizard if `.env` is already configured with `LLM_MODEL`.

### Changed
- Reorganized README structure and simplified installation instructions.
- Renamed default admin user from `hamish` to `user`.

---

## [2026-02-17] — Initial Release

### Added
- **Autonomous book writing** with a 5-phase agentic pipeline: Planning → Research → Writing → Editing → Refining.
- **Professional tools** modeled after coding agents: `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirectoryTool`, `SearchFilesTool`, `GrepSearchTool`, `DeleteFileTool`.
- **Multiple LLM support**: OpenAI, Ollama, LM Studio, and custom OpenAI-compatible endpoints.
- **Real-time monitoring**: Live progress dashboard with activity feeds.
- **Agent chat**: Interactive chat to guide the writing process.
- **Export formats**: PDF, EPUB, DOCX, and plain text.
- **Character management** and **plot tracking**.
- User authentication, profile management.
- Community link to Skool and company attribution (A-Tech Corporation PTY LTD).

---

## Versioning Notes

BookGPT uses date-based changelog entries rather than semantic versioning. Each entry represents a significant batch of changes deployed to the `main` branch. For the complete commit history, see `git log`.