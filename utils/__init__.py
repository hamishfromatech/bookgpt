"""
Utils package for BookGPT.

This package provides utility modules for database and LLM client functionality.
"""

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