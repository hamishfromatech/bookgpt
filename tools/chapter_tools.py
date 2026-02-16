"""
Chapter Tools for BookGPT Agent.

NOTE: This module is deprecated. Chapter writing is now handled directly by the 
BookWritingAgent using LLM calls. File operations are handled by file_tools.py.

This file is kept for backwards compatibility but may be removed in future versions.
"""

# The chapter writing and editing functionality has been moved to:
# - book_agent.py: LLM-powered chapter generation
# - tools/file_tools.py: File read/write/edit operations

from .file_tools import BaseTool, WriteFileTool, ReadFileTool, EditFileTool

# Re-export for backwards compatibility
__all__ = ['BaseTool', 'WriteFileTool', 'ReadFileTool', 'EditFileTool']
