"""LLM client must not crash when a provider omits `response.usage`.

OpenAI-compatible local providers (Ollama, LM Studio, vLLM) frequently return
`usage=None` on non-streaming responses. The old code dereferenced
`response.usage.prompt_tokens` unconditionally and raised AttributeError.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from utils.llm_client import LLMClient, _safe_usage


class TestSafeUsage:
    def test_none_usage_returns_zeros(self):
        result = _safe_usage(None)
        assert result == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_partial_usage_is_filled(self):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=None, total_tokens=None)
        result = _safe_usage(usage)
        assert result == {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 0}

    def test_full_usage_passes_through(self):
        usage = SimpleNamespace(prompt_tokens=5, completion_tokens=7, total_tokens=12)
        assert _safe_usage(usage) == {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}


def _make_response(content="hi", tool_calls=None, usage=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice], usage=usage)


class TestChatGuardsNullUsage:
    def test_chat_with_none_usage_does_not_crash(self):
        client = LLMClient(api_key="sk-dummy")
        client._client = MagicMock()
        client._client.chat.completions.create.return_value = _make_response(usage=None)

        resp = client.chat([{"role": "user", "content": "ping"}], max_tokens=5)
        assert resp.content == "hi"
        assert resp.usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_chat_with_real_usage_passes_through(self):
        client = LLMClient(api_key="sk-dummy")
        client._client = MagicMock()
        usage = SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5)
        client._client.chat.completions.create.return_value = _make_response(usage=usage)

        resp = client.chat([{"role": "user", "content": "ping"}])
        assert resp.usage["total_tokens"] == 5


class TestChatWithToolsGuardsNullUsage:
    def test_chat_with_tools_none_usage_does_not_crash(self):
        client = LLMClient(api_key="sk-dummy")
        client._client = MagicMock()
        client._client.chat.completions.create.return_value = _make_response(usage=None)

        resp = client.chat_with_tools(
            [{"role": "user", "content": "do something"}],
            tools=[{"type": "function", "function": {"name": "t", "description": "d", "parameters": {}}}],
        )
        assert resp.content == "hi"
        assert resp.usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def test_chat_with_tools_propagates_tool_calls(self):
        client = LLMClient(api_key="sk-dummy")
        client._client = MagicMock()
        tc = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="write_file", arguments='{"path":"a.md"}'),
        )
        msg = SimpleNamespace(content=None, tool_calls=[tc])
        choice = SimpleNamespace(message=msg)
        client._client.chat.completions.create.return_value = SimpleNamespace(
            choices=[choice], usage=None
        )

        resp = client.chat_with_tools(
            [{"role": "user", "content": "write"}],
            tools=[{"type": "function", "function": {"name": "write_file", "description": "d", "parameters": {}}}],
        )
        assert resp.has_tool_calls
        assert resp.tool_calls[0]["function"]["name"] == "write_file"