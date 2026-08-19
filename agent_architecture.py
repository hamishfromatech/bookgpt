"""
Multi-Agent Architecture for BookGPT.

This module implements a multi-agent system using the SupervisorMode pattern,
with specialized sub-agents for different writing tasks:
- Planning Agent: Creates outlines and story structure
- Writing Agent: Generates chapter content with creative focus
- Editing Agent: Handles grammar, consistency, and style improvements
- Consistency Agent: Monitors character names, locations, and plot coherence

The Supervisor coordinates these agents based on task requirements.
"""

import json
from typing import List, Dict, Any, Optional, Callable
from utils.llm_client import (
    LLMClient,
    ToolDefinition,
    SubAgent,
    SupervisorMode,
    get_llm_client
)


class BookWritingAgents:
    """
    Collection of specialized sub-agents for book writing tasks.
    """
    
    @staticmethod
    def create_planning_agent(llm_client: LLMClient) -> SubAgent:
        """Create a planning agent focused on outline and story structure."""
        system_message = """You are an expert book planner and outline creator. Your role is to create 
detailed, compelling book outlines that serve as the foundation for a complete novel.

When creating an outline, consider:
- Genre conventions and reader expectations
- Character development arcs
- Plot structure (setup, rising action, climax, resolution)
- Pacing and chapter distribution
- Themes and motifs

Provide structured, detailed outlines that will guide the writing process."""
        
        return SubAgent(
            name="planning_agent",
            system_message=system_message,
            tools=[],  # Planning agent primarily uses LLM reasoning
            llm_client=llm_client,
            max_iterations=10
        )
    
    @staticmethod
    def create_writing_agent(llm_client: LLMClient, tools: List[ToolDefinition]) -> SubAgent:
        """Create a writing agent focused on chapter content generation."""
        system_message = """You are a skilled fiction writer. Your role is to write engaging, 
well-crafted chapters that bring the story to life. 

Focus on:
- Vivid, sensory descriptions
- Natural dialogue that reveals character
- Proper pacing and scene structure
- Emotional resonance
- Consistent voice and style

Write complete, polished chapters that advance the plot while developing characters."""
        
        return SubAgent(
            name="writing_agent",
            system_message=system_message,
            tools=tools,
            llm_client=llm_client,
            max_iterations=15
        )
    
    @staticmethod
    def create_editing_agent(llm_client: LLMClient, tools: List[ToolDefinition]) -> SubAgent:
        """Create an editing agent for grammar, consistency, and style improvements."""
        system_message = """You are a professional book editor. Your role is to review and improve 
written content for clarity, consistency, and quality.

Focus on:
- Narrative flow and pacing
- Character consistency
- Plot coherence
- Dialogue quality
- Language and style improvements
- Grammar and punctuation

Use targeted edits rather than complete rewrites when possible."""
        
        return SubAgent(
            name="editing_agent",
            system_message=system_message,
            tools=tools,
            llm_client=llm_client,
            max_iterations=20
        )
    
    @staticmethod
    def create_consistency_agent(llm_client: LLMClient, tools: List[ToolDefinition]) -> SubAgent:
        """Create a consistency agent for monitoring character names, locations, and plot coherence."""
        system_message = """You are a story continuity specialist. Your role is to ensure consistency 
across the manuscript by tracking:

- Character names, descriptions, and actions remain consistent
- Location mentions align across chapters
- Plot timelines and events don't contradict each other
- Genre conventions and world-building rules are maintained

Use grep_search and read_file tools to verify consistency across chapters."""
        
        return SubAgent(
            name="consistency_agent",
            system_message=system_message,
            tools=tools,
            llm_client=llm_client,
            max_iterations=15
        )


class BookSupervisor:
    """
    Supervisor agent that coordinates multiple specialized sub-agents for book writing.
    
    Uses the SupervisorMode pattern to delegate tasks to appropriate specialists:
    - planning_agent: For outline and structure creation
    - writing_agent: For chapter content generation
    - editing_agent: For grammar, consistency, and style improvements
    - consistency_agent: For monitoring character names, locations, and plot coherence
    """
    
    def __init__(self, llm_client: LLMClient, tools: List[ToolDefinition]):
        self.llm_client = llm_client
        
        # Create specialized sub-agents
        agents = {
            'planning_agent': BookWritingAgents.create_planning_agent(llm_client),
            'writing_agent': BookWritingAgents.create_writing_agent(llm_client, tools),
            'editing_agent': BookWritingAgents.create_editing_agent(llm_client, tools),
            'consistency_agent': BookWritingAgents.create_consistency_agent(llm_client, tools)
        }
        
        # Supervisor system message
        system_message = """You are a Supervisor AI coordinating specialized writing agents for book production.

Available Specialists:
- planning_agent: Expert in creating detailed chapter-by-chapter outlines and story structure
- writing_agent: Skilled fiction writer who generates engaging chapter content
- editing_agent: Professional book editor focused on clarity, consistency, and quality improvements
- consistency_agent: Story continuity specialist ensuring character names, locations, and plot coherence

Your role is to delegate tasks to the appropriate specialist based on the task requirements.
Use the delegate_to_[agent_name] tool to assign work."""
        
        self.supervisor = SupervisorMode(
            agents=agents,
            system_message=system_message,
            llm_client=llm_client,
            max_delegations=5
        )
    
    def process_task(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a writing task using the supervisor and specialized agents."""
        messages = [{"role": "user", "content": task}]
        
        # Custom delegate callback to handle agent execution
        def delegate_callback(agent_name: str, task_str: str, context_dict: Dict[str, Any]) -> Dict[str, Any]:
            if agent_name in self.supervisor.agents:
                return self.supervisor.agents[agent_name].run(task_str, context=context_dict)
            return {"error": f"Unknown agent: {agent_name}"}
        
        return self.supervisor.run(
            messages=messages,
            delegate_callback=delegate_callback
        )
    
    def process_task_stream(self, task: str, context: Optional[Dict[str, Any]] = None):
        """Process a writing task using streaming with the supervisor and specialized agents."""
        messages = [{"role": "user", "content": task}]
        
        # Custom delegate callback to handle agent execution
        def delegate_callback(agent_name: str, task_str: str, context_dict: Dict[str, Any]) -> Dict[str, Any]:
            if agent_name in self.supervisor.agents:
                return self.supervisor.agents[agent_name].run(task_str, context=context_dict)
            return {"error": f"Unknown agent: {agent_name}"}
        
        for update in self.supervisor.run_stream(messages, delegate_callback=delegate_callback):
            yield update