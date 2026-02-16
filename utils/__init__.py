"""
Utils package for BookGPT.

This package provides utility modules for storage and LLM client functionality.
"""

from .storage import BookStorage
from .llm_client import (
    LLMClient,
    LLMConfig,
    LLMResponse,
    LLMProvider,
    ChatMessage,
    ToolDefinition,
    create_openai_client,
    create_local_client,
    create_ollama_client,
    create_lmstudio_client
)

__all__ = [
    'BookStorage',
    'LLMClient',
    'LLMConfig',
    'LLMResponse',
    'LLMProvider',
    'ChatMessage',
    'ToolDefinition',
    'create_openai_client',
    'create_local_client',
    'create_ollama_client',
    'create_lmstudio_client'
]
