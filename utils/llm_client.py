import os
import json
import logging
from typing import Dict, Any, List, Optional, Union, Generator, Callable, TypeVar
from dataclasses import dataclass, field
from enum import Enum
import openai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MOCK = "mock"

@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4-turbo-preview"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: float = 60.0
    extra_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ChatMessage:
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]

@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Any = None
    
    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

class LLMClient:
    """Client for interacting with LLM providers."""
    
    def __init__(self, config: Optional[LLMConfig] = None, **kwargs):
        if config:
            self.config = config
        else:
            # Fallback for direct keyword arguments
            provider_str = kwargs.get('provider', 'openai')
            try:
                provider = LLMProvider(provider_str)
            except ValueError:
                provider = LLMProvider.OPENAI
                
            self.config = LLMConfig(
                provider=provider,
                model=kwargs.get('model', "gpt-4-turbo-preview"),
                api_key=kwargs.get('api_key'),
                base_url=kwargs.get('base_url'),
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 4000)
            )
        self._setup_client()
    
    def _setup_client(self):
        if self.config.provider == LLMProvider.OPENAI:
            # We use a dummy key if none provided to allow initialization
            # but actual calls will fail unless base_url redirects elsewhere or key is set later
            api_key = self.config.api_key or os.getenv("OPENAI_API_KEY") or "sk-dummy-key-for-init"
            
            self._client = openai.OpenAI(
                api_key=api_key,
                base_url=self.config.base_url or os.getenv("OPENAI_BASE_URL")
            )
        else:
            # Add other providers as needed
            raise ValueError(f"Provider {self.config.provider} not supported yet")

    def test_connection(self) -> Dict[str, Any]:
        """Test the connection to the LLM provider."""
        try:
            # Simple small token test
            response = self.chat([
                {"role": "user", "content": "ping"}
            ], max_tokens=5)
            
            return {
                "success": True,
                "response": response.content,
                "usage": response.usage
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _format_messages(self, messages: List[Union[Dict[str, Any], ChatMessage]]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            if isinstance(msg, dict):
                formatted.append(msg)
            else:
                d = {"role": msg.role, "content": msg.content}
                if msg.name: d["name"] = msg.name
                if msg.tool_calls: d["tool_calls"] = msg.tool_calls
                if msg.tool_call_id: d["tool_call_id"] = msg.tool_call_id
                formatted.append(d)
        return formatted

    def _format_tools(self, tools: List[Union[Dict[str, Any], ToolDefinition]]) -> List[Dict[str, Any]]:
        formatted = []
        for tool in tools:
            if isinstance(tool, dict):
                formatted.append(tool)
            else:
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                })
        return formatted

    def chat(self, messages: List[Union[Dict[str, Any], ChatMessage]], **kwargs) -> LLMResponse:
        formatted_messages = self._format_messages(messages)
        params = {
            "model": kwargs.pop("model", self.config.model),
            "messages": formatted_messages,
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            **kwargs
        }
        
        try:
            response = self._client.chat.completions.create(**params)
            choice = response.choices[0]
            
            return LLMResponse(
                content=choice.message.content,
                tool_calls=[], # Standard chat doesn't have tool calls in this helper
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise

    def chat_with_tools(
        self, 
        messages: List[Union[Dict[str, Any], ChatMessage]], 
        tools: List[Union[Dict[str, Any], ToolDefinition]],
        **kwargs
    ) -> LLMResponse:
        formatted_messages = self._format_messages(messages)
        formatted_tools = self._format_tools(tools)
        
        params = {
            "model": kwargs.pop("model", self.config.model),
            "messages": formatted_messages,
            "tools": formatted_tools,
            "tool_choice": kwargs.pop("tool_choice", "auto"),
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            **kwargs
        }
        
        try:
            response = self._client.chat.completions.create(**params)
            choice = response.choices[0]
            tool_calls = []
            
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })
            
            return LLMResponse(
                content=choice.message.content,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                raw_response=response
            )
        except Exception as e:
            logger.error(f"Chat with tools error: {e}")
            raise

    def chat_stream(self, messages: List[Union[Dict[str, Any], ChatMessage]], **kwargs) -> Generator[str, None, None]:
        formatted_messages = self._format_messages(messages)
        params = {
            "model": kwargs.pop("model", self.config.model),
            "messages": formatted_messages,
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            "stream": True,
            **kwargs
        }
        
        try:
            stream = self._client.chat.completions.create(**params)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            raise

    def chat_stream_with_tools(
        self,
        messages: List[Union[Dict[str, Any], ChatMessage]],
        tools: List[Union[Dict[str, Any], ToolDefinition]],
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream a chat completion response with tool calling support.
        """
        formatted_messages = self._format_messages(messages)
        formatted_tools = self._format_tools(tools)
        
        params = {
            "model": kwargs.pop("model", self.config.model),
            "messages": formatted_messages,
            "tools": formatted_tools,
            "tool_choice": kwargs.pop("tool_choice", "auto"),
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            "stream": True,
            **kwargs
        }
        
        if self.config.provider == LLMProvider.OPENAI:
            params["stream_options"] = {"include_usage": True}
        
        try:
            stream = self._client.chat.completions.create(**params)
            
            content_chunks = []
            current_tool_calls = {}
            final_usage = None
            
            for chunk in stream:
                if hasattr(chunk, 'usage') and chunk.usage:
                    final_usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens
                    }

                if not chunk.choices:
                    continue
                    
                delta = chunk.choices[0].delta
                
                # 1. Handle content
                if delta.content:
                    content_chunks.append(delta.content)
                    yield {
                        'type': 'content',
                        'data': delta.content
                    }
                
                # 2. Handle tool call chunks
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = str(tc_chunk.index)
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                'id': tc_chunk.id,
                                'type': 'function',
                                'function': {
                                    'name': tc_chunk.function.name or '',
                                    'arguments': tc_chunk.function.arguments or ''
                                }
                            }
                            # Signal UI that a tool call started IF we have an ID
                            if tc_chunk.id:
                                yield {
                                    'type': 'tool_call_start',
                                    'data': {
                                        'id': tc_chunk.id,
                                        'name': tc_chunk.function.name
                                    }
                                }
                        else:
                            # Accumulate arguments
                            if tc_chunk.function.arguments:
                                current_tool_calls[idx]['function']['arguments'] += tc_chunk.function.arguments
                            # If ID appears in later chunk for same index
                            if tc_chunk.id and not current_tool_calls[idx]['id']:
                                current_tool_calls[idx]['id'] = tc_chunk.id
                                yield {
                                    'type': 'tool_call_start',
                                    'data': {
                                        'id': tc_chunk.id,
                                        'name': current_tool_calls[idx]['function']['name']
                                    }
                                }
            
            # 3. After stream finishes, yield the COMPLETED tool calls
            full_content = ''.join(content_chunks)
            completed_tools = [v for v in current_tool_calls.values() if v.get('id') and v['function'].get('name')]
            
            for tc in completed_tools:
                yield {
                    'type': 'tool_call',
                    'data': tc
                }
                
            yield {
                'type': 'complete',
                'data': {
                    'content': full_content,
                    'tool_calls': completed_tools,
                    'usage': final_usage
                }
            }
                    
        except Exception as e:
            logger.error(f"Chat stream with tools error: {e}")
            raise


# Global client management
_llm_client = None

def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _llm_client
    if _llm_client is None:
        # Load config from env or DB
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model=os.getenv("LLM_MODEL", "gpt-4-turbo-preview"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        _llm_client = LLMClient(config)
    return _llm_client

def reset_llm_client():
    """Reset the global LLM client (useful when settings change)."""
    global _llm_client
    _llm_client = None


def create_openai_client(api_key: str, model: str = "gpt-4", temperature: float = 0.7, max_tokens: int = 4000) -> LLMClient:
    return LLMClient(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=LLMProvider.OPENAI
    )

def create_local_client(base_url: str, model: str = "local-model", temperature: float = 0.7, max_tokens: int = 4000) -> LLMClient:
    return LLMClient(
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key="not-needed"
    )

def create_ollama_client(base_url: str = "http://localhost:11434/v1", model: str = "llama3", temperature: float = 0.7) -> LLMClient:
    return LLMClient(
        base_url=base_url,
        model=model,
        temperature=temperature,
        api_key="ollama"
    )

def create_lmstudio_client(base_url: str = "http://localhost:1234/v1", model: str = "local-model", temperature: float = 0.7) -> LLMClient:
    return LLMClient(
        base_url=base_url,
        model=model,
        temperature=temperature,
        api_key="lm-studio"
    )


# Type alias for tool functions
ToolFunction = TypeVar('ToolFunction', bound=Callable[..., Any])


class AgentMode:
    """
    Agentic mode that handles iterative tool calling with proper message loop.
    
    This class implements the complete agent loop pattern from OpenAI's documentation:
    1. Send messages to LLM
    2. If LLM returns tool calls → execute each tool
    3. Add tool results as role="tool" messages
    4. Loop back to step 1 with ALL messages
    5. Return final response when no more tool calls
    
    Example:
        agent = AgentMode(
            client=llm_client,
            tools=[get_weather, search_web],
            system_message="You are a helpful assistant."
        )
        result = agent.run(
            messages=[{"role": "user", "content": "What's the weather in Paris?"}]
        )
    """
    
    def __init__(
        self,
        client: LLMClient,
        tools: List[ToolDefinition],
        system_message: str,
        max_iterations: int = 20,
        temperature: Optional[float] = None
    ):
        """
        Initialize the agent mode.
        
        Args:
            client: LLMClient instance for making API calls
            tools: List of available tool definitions
            system_message: System prompt for the agent
            max_iterations: Maximum number of tool-calling iterations
            temperature: Optional temperature override
        """
        self.client = client
        self.tools = {tool.name: tool for tool in tools}
        self.tool_definitions = tools
        self.system_message = system_message
        self.max_iterations = max_iterations
        self.temperature = temperature
    
    def run(
        self,
        messages: List[Dict[str, Any]],
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        final_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Run the full agentic loop with tool calling.
        
        Args:
            messages: Initial messages (will be modified with tool results)
            tool_executor: Optional custom function to execute tools.
                          If None, uses default executor that looks up by name.
            context: Optional context passed to every tool call
            final_callback: Optional callback for streaming final response
            
        Returns:
            Dict with 'content', 'tool_results', 'iterations', 'finished'
        """
        # Build the full message list
        full_messages = [{"role": "system", "content": self.system_message}]
        full_messages.extend(messages if isinstance(messages, list) else [messages])
        
        iterations = 0
        tool_results = []
        
        while iterations < self.max_iterations:
            iterations += 1
            
            # Make the API call
            response = self.client.chat_with_tools(
                messages=full_messages,
                tools=self.tool_definitions,
                temperature=self.temperature,
                tool_choice="auto"
            )
            
            # Get the assistant message
            assistant_msg = {
                "role": "assistant",
                "content": response.content or ""
            }
            
            # Add tool calls if present
            if response.has_tool_calls:
                assistant_msg["tool_calls"] = response.tool_calls
            
            full_messages.append(assistant_msg)
            
            # If no tool calls, we're done
            if not response.has_tool_calls:
                if final_callback:
                    final_callback(response.content or "")
                return {
                    "content": response.content,
                    "tool_results": tool_results,
                    "iterations": iterations,
                    "finished": True,
                    "usage": response.usage
                }
            
            # Execute tool calls
            for tc in response.tool_calls:
                tool_name = tc['function']['name']
                try:
                    args = json.loads(tc['function']['arguments'] or '{}')
                except json.JSONDecodeError:
                    args = {}
                
                # Add context if provided
                if context:
                    args.update(context)
                
                # Execute the tool
                tool_result = None
                if tool_executor:
                    tool_result = tool_executor(tool_name, args)
                elif tool_name in self.tools:
                    try:
                        tool_result = self.tools[tool_name].execute(**args)
                    except Exception as e:
                        tool_result = {"success": False, "error": str(e)}
                else:
                    tool_result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                
                # Convert result to string
                result_content = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                
                # Create tool result message
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": tool_name,
                    "content": result_content
                }
                full_messages.append(tool_msg)
                
                tool_results.append({
                    "tool_call_id": tc['id'],
                    "tool_name": tool_name,
                    "arguments": args,
                    "result": tool_result,
                    "success": isinstance(tool_result, dict) and tool_result.get("success", True)
                })
        
        # Max iterations reached
        return {
            "content": "Agent reached maximum iteration limit. Some tasks may not be complete.",
            "tool_results": tool_results,
            "iterations": iterations,
            "finished": False,
            "error": "max_iterations_reached"
        }
    
    def run_stream(
        self,
        messages: List[Dict[str, Any]],
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Run the agentic loop with streaming support.
        """
        full_messages = [{"role": "system", "content": self.system_message}]
        full_messages.extend(messages if isinstance(messages, list) else [messages])
        
        iterations = 0
        tool_results = []
        
        while iterations < self.max_iterations:
            iterations += 1
            
            # Stream this turn
            content_buffer = ""
            tool_calls_in_turn = []
            tool_results_in_turn = []
            
            for update in self.client.chat_stream_with_tools(
                messages=full_messages,
                tools=self.tool_definitions,
                temperature=self.temperature
            ):
                if update['type'] == 'content':
                    content_buffer += update['data']
                    yield update
                elif update['type'] == 'tool_call':
                    tc = update['data']
                    tool_calls_in_turn.append(tc)
                    yield update
                elif update['type'] == 'complete':
                    break
            
            if not tool_calls_in_turn:
                # No tool calls, we're done
                yield {'type': 'complete', 'data': {
                    'content': content_buffer,
                    'iterations': iterations,
                    'finished': True
                }}
                return
            
            # Add assistant message
            assistant_msg = {
                "role": "assistant",
                "content": content_buffer,
                "tool_calls": tool_calls_in_turn
            }
            full_messages.append(assistant_msg)
            
            # Execute tool calls
            for tc in tool_calls_in_turn:
                tool_name = tc['function']['name']
                try:
                    args = json.loads(tc['function']['arguments'] or '{}')
                except json.JSONDecodeError:
                    args = {}
                
                if context:
                    args.update(context)
                
                # Execute
                tool_result = None
                if tool_executor:
                    tool_result = tool_executor(tool_name, args)
                elif tool_name in self.tools:
                    try:
                        tool_result = self.tools[tool_name].execute(**args)
                    except Exception as e:
                        tool_result = {"success": False, "error": str(e)}
                else:
                    tool_result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                
                result_content = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": tool_name,
                    "content": result_content
                }
                full_messages.append(tool_msg)
                
                tool_results.append({
                    "tool_call_id": tc['id'],
                    "tool_name": tool_name,
                    "arguments": args,
                    "result": tool_result
                })
                
                yield {
                    'type': 'tool_result',
                    'data': {
                        'tool_call_id': tc['id'],
                        'tool_name': tool_name,
                        'result': tool_result
                    }
                }
            
            yield {'type': 'turn_complete', 'data': {'iteration': iterations}}
        
        # Max iterations reached
        yield {'type': 'complete', 'data': {
            'content': "Agent reached maximum iteration limit.",
            'iterations': iterations,
            'finished': False
        }}


class SubAgent:
    """
    A sub-agent that can be used by a supervisor.
    """
    
    def __init__(
        self,
        name: str,
        system_message: str,
        tools: List[ToolDefinition],
        llm_client: Optional[LLMClient] = None,
        max_iterations: int = 10
    ):
        self.name = name
        self.system_message = system_message
        self.tools = tools
        self.llm_client = llm_client
        self.max_iterations = max_iterations
    
    def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Run the sub-agent on a task."""
        client = self.llm_client or get_llm_client()
        
        agent = AgentMode(
            client=client,
            tools=self.tools,
            system_message=self.system_message,
            max_iterations=self.max_iterations
        )
        
        messages = [{"role": "user", "content": task}]
        if history:
            messages = history + messages
        
        return agent.run(messages, context=context)


class SupervisorMode:
    """
    Supervisor/Manager agent that coordinates multiple specialized sub-agents.
    """
    
    def __init__(
        self,
        agents: Dict[str, SubAgent],
        system_message: str,
        llm_client: Optional[LLMClient] = None,
        max_delegations: int = 5
    ):
        self.agents = agents
        self.system_message = system_message
        self.llm_client = llm_client
        self.max_delegations = max_delegations
        
        # Build tool definitions for calling sub-agents
        self.sub_agent_tools = [
            ToolDefinition(
                name=f"delegate_to_{name}",
                description=(
                    f"Delegate a task to the {name} specialist. "
                    f"Use this when the task requires {name}'s expertise."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The specific task to delegate"
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context for the task"
                        }
                    },
                    "required": ["task"]
                }
            )
            for name in agents.keys()
        ]
    
    def run(
        self,
        messages: List[Dict[str, Any]],
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        delegate_callback: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Run the supervisor with potential delegation."""
        client = self.llm_client or get_llm_client()
        
        all_messages = [{"role": "system", "content": self.system_message}]
        all_messages.extend(messages if isinstance(messages, list) else [messages])
        
        delegations = []
        iterations = 0
        
        while iterations < self.max_delegations:
            iterations += 1
            
            response = client.chat_with_tools(
                messages=all_messages,
                tools=self.sub_agent_tools,
                tool_choice="auto"
            )
            
            assistant_msg = {
                "role": "assistant",
                "content": response.content or ""
            }
            if response.has_tool_calls:
                assistant_msg["tool_calls"] = response.tool_calls
            
            all_messages.append(assistant_msg)
            
            if not response.has_tool_calls:
                return {
                    "content": response.content,
                    "delegations": delegations,
                    "iterations": iterations,
                    "finished": True
                }
            
            # Handle delegation tool calls
            for tc in response.tool_calls:
                tool_name = tc['function']['name']
                
                if not tool_name.startswith("delegate_to_"):
                    # Handle non-delegation tools
                    if tool_executor:
                        args = json.loads(tc['function']['arguments'] or '{}')
                        result = tool_executor(tool_name, args)
                    else:
                        result = {"error": f"Unknown function: {tool_name}"}
                else:
                    # It's a delegation
                    agent_name = tool_name.replace("delegate_to_", "")
                    args = json.loads(tc['function']['arguments'] or '{}')
                    task = args.get("task", "")
                    context = args.get("context", {})
                    
                    delegations.append({
                        "agent": agent_name,
                        "task": task,
                        "tool_call_id": tc['id']
                    })
                    
                    if delegate_callback:
                        result = delegate_callback(agent_name, task, context)
                    elif agent_name in self.agents:
                        result = self.agents[agent_name].run(task, context=context)
                    else:
                        result = {"error": f"Unknown agent: {agent_name}"}
                
                result_content = json.dumps(result) if isinstance(result, dict) else str(result)
                
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": tool_name,
                    "content": result_content
                })
        
        return {
            "content": "Supervisor reached maximum delegation limit.",
            "delegations": delegations,
            "iterations": iterations,
            "finished": False,
            "error": "max_delegations_reached"
        }
    
    def run_stream(
        self,
        messages: List[Dict[str, Any]],
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        delegate_callback: Optional[Callable[[str, str, Dict[str, Any]], Dict[str, Any]]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Run supervisor with streaming and delegation support."""
        client = self.llm_client or get_llm_client()
        
        all_messages = [{"role": "system", "content": self.system_message}]
        all_messages.extend(messages if isinstance(messages, list) else [messages])
        
        delegations = []
        iterations = 0
        
        while iterations < self.max_delegations:
            iterations += 1
            
            content_buffer = ""
            tool_calls_in_turn = []
            
            for update in client.chat_stream_with_tools(
                messages=all_messages,
                tools=self.sub_agent_tools
            ):
                if update['type'] == 'content':
                    content_buffer += update['data']
                    yield update
                elif update['type'] == 'tool_call':
                    tool_calls_in_turn.append(update['data'])
                    yield update
                elif update['type'] == 'complete':
                    break
            
            if not tool_calls_in_turn:
                yield {'type': 'complete', 'data': {
                    'content': content_buffer,
                    'delegations': delegations,
                    'finished': True
                }}
                return
            
            # Add assistant message
            all_messages.append({
                "role": "assistant",
                "content": content_buffer,
                "tool_calls": tool_calls_in_turn
            })
            
            # Handle delegations
            for tc in tool_calls_in_turn:
                tool_name = tc['function']['name']
                
                if tool_name.startswith("delegate_to_"):
                    agent_name = tool_name.replace("delegate_to_", "")
                    args = json.loads(tc['function']['arguments'] or '{}')
                    task = args.get("task", "")
                    context = args.get("context", {})
                    
                    delegations.append({
                        "agent": agent_name,
                        "task": task,
                        "tool_call_id": tc['id']
                    })
                    
                    yield {
                        'type': 'delegation_start',
                        'data': {
                            'agent': agent_name,
                            'task': task,
                            'tool_call_id': tc['id']
                        }
                    }
                    
                    if delegate_callback:
                        result = delegate_callback(agent_name, task, context)
                    elif agent_name in self.agents:
                        result = self.agents[agent_name].run(task, context=context)
                    else:
                        result = {"error": f"Unknown agent: {agent_name}"}
                    
                    yield {
                        'type': 'delegation_result',
                        'data': {
                            'agent': agent_name,
                            'tool_call_id': tc['id'],
                            'result': result
                        }
                    }
                else:
                    # Handle non-delegation tools
                    if tool_executor:
                        args = json.loads(tc['function']['arguments'] or '{}')
                        result = tool_executor(tool_name, args)
                    else:
                        result = {"error": f"Unknown function: {tool_name}"}
                
                result_content = json.dumps(result) if isinstance(result, dict) else str(result)
                
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": tool_name,
                    "content": result_content
                })
            
            yield {'type': 'turn_complete', 'data': {'iteration': iterations}}
        
        yield {'type': 'complete', 'data': {
            'content': "Supervisor reached maximum delegation limit.",
            'delegations': delegations,
            'finished': False
        }}
