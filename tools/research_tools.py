"""
Research Tools - DEPRECATED

This module has been removed. Research functionality is now handled directly
by the BookWritingAgent using LLM calls, similar to how writing and editing
are handled.

The ResearchTool and OutlineTool were generating fake/template content, which
was inconsistent with the LLM-powered approach used for other phases.

For research and outline generation, see:
- book_agent.py: _execute_planning_phase() and _execute_research_phase()

This file is kept for backwards compatibility but will be removed in a future version.
"""

# Empty module - all functionality moved to book_agent.py