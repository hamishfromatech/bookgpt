"""
Tools package for BookGPT Agent.

This package provides professional file operation tools for the BookGPT agent.
The tools are modeled after coding agents like Cursor, Windsurf, Aider, and OpenAI Codex.

File Tools:
- ReadFileTool: Read file contents with line range support
- WriteFileTool: Create or overwrite files
- EditFileTool: Search and replace in files
- ListDirectoryTool: List directory contents
- SearchFilesTool: Search for files by name pattern
- GrepSearchTool: Search for content within files
- DeleteFileTool: Delete files

Note: Research and outline functionality has moved to the BookWritingAgent
and is handled directly by the LLM, similar to writing and editing phases.
"""

from .file_tools import (
    BaseTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirectoryTool,
    SearchFilesTool,
    GrepSearchTool,
    DeleteFileTool,
    get_file_tools,
    ALL_FILE_TOOLS
)

__all__ = [
    # Base class
    'BaseTool',
    
    # File tools
    'ReadFileTool',
    'WriteFileTool', 
    'EditFileTool',
    'ListDirectoryTool',
    'SearchFilesTool',
    'GrepSearchTool',
    'DeleteFileTool',
    'get_file_tools',
    'ALL_FILE_TOOLS',
]