"""
Agent Factory for BookGPT.
Centralizes agent creation and management.
"""

import logging
from book_agent import BookWritingAgent
from utils.llm_client import get_llm_client
from utils.database import BookDatabase
from tools.file_tools import (
    ReadFileTool, 
    WriteFileTool, 
    EditFileTool, 
    ListDirectoryTool, 
    SearchFilesTool, 
    GrepSearchTool, 
    DeleteFileTool
)

logger = logging.getLogger(__name__)

# Global tool registry
ALL_TOOLS = {
    'read_file': ReadFileTool(),
    'write_file': WriteFileTool(),
    'edit_file': EditFileTool(),
    'list_directory': ListDirectoryTool(),
    'search_files': SearchFilesTool(),
    'grep_search': GrepSearchTool(),
    'delete_file': DeleteFileTool()
}

# Global agent instance
_agent = None

def get_agent() -> BookWritingAgent:
    """Get or create the global agent instance."""
    global _agent
    if _agent is None:
        llm_client = get_llm_client()
        tools_list = list(ALL_TOOLS.values())
        db = BookDatabase()
        _agent = BookWritingAgent(tools=tools_list, llm_client=llm_client, db=db)
        logger.info("Global BookWritingAgent initialized")
    return _agent

def reset_agent():
    """Reset the global agent instance."""
    global _agent
    _agent = None
