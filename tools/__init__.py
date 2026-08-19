"""
Tools package for BookGPT Agent.

This package provides professional file operation tools and writing-specific tools 
for the BookGPT agent. The tools are modeled after coding agents like Cursor, Windsurf, 
Aider, and OpenAI Codex.

File Tools:
- ReadFileTool: Read file contents with line range support
- WriteFileTool: Create or overwrite files
- EditFileTool: Search and replace in files
- ListDirectoryTool: List directory contents
- SearchFilesTool: Search for files by name pattern
- GrepSearchTool: Search for content within files
- DeleteFileTool: Delete files

Writing-Specific Tools:
- RunningSummaryTool: Maintain story context across chapters
- ChapterEvaluationTool: Analyze chapter quality and identify improvements
- CharacterConsistencyTool: Track and verify character mentions across chapters
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

from .writing_tools import (
    RunningSummaryTool,
    ChapterEvaluationTool,
    CharacterConsistencyTool
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
    
    # Writing tools
    'RunningSummaryTool',
    'ChapterEvaluationTool',
    'CharacterConsistencyTool',
]