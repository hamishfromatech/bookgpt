"""
Book Writing Agent - Implements agentic loop with tool calling for autonomous book writing.

This agent uses OpenAI (or OpenAI-compatible APIs) for real AI-powered book generation,
following the patterns from OpenAI's function calling and coding agent templates.
"""

import json
import uuid
import os
import time
import threading
from typing import List, Dict, Any, Optional, Generator, Callable
from datetime import datetime
import logging
from functools import wraps

from utils.llm_client import (
    LLMClient,
    LLMConfig,
    LLMResponse,
    ToolDefinition,
    ChatMessage,
    AgentMode,
    SubAgent,
    SupervisorMode,
    create_openai_client,
    create_local_client,
    create_ollama_client
)



from utils.database import BookDatabase
from models.book_model import BookProject

# Import BaseTool from tools package
from tools.file_tools import BaseTool

logger = logging.getLogger(__name__)


# =============================================================================
# RETRY LOGIC
# =============================================================================

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0,
                       exceptions: tuple = (Exception,)):
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
                        raise

            raise last_exception
        return wrapper
    return decorator


class ToolCall:
    """Represents a tool call in the agent's execution loop."""
    
    def __init__(self, tool_name: str, arguments: Dict[str, Any], id: str = None):
        self.id = id or str(uuid.uuid4())
        self.tool_name = tool_name
        self.arguments = arguments
        self.result = None
        self.error = None
        self.timestamp = datetime.now()


class AgentResponse:
    """Represents the agent's response after tool execution."""
    
    def __init__(self, content: str, tool_calls: List[ToolCall] = None, finished: bool = False):
        self.content = content
        self.tool_calls = tool_calls or []
        self.finished = finished
        self.timestamp = datetime.now()


class AgentActivityLog:
    """Represents an activity log entry for agent tool calls and reasoning."""
    
    def __init__(self, phase: str, action: str, details: Dict[str, Any], timestamp: datetime = None):
        self.phase = phase
        self.action = action
        self.details = details
        self.timestamp = timestamp or datetime.now()
        self.id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'phase': self.phase,
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class BookWritingAgent:
    """
    Main agent for autonomous book writing using agentic loops and tool calling.
    
    This agent supports:
    1. OpenAI API (default)
    2. Custom base URLs for OpenAI-compatible APIs
    3. Local LLM servers (Ollama, LM Studio, vLLM, etc.)
    4. Domain-specific writing skills (fiction-writer, non-fiction-author, academic-writer, childrens-book-creator, screenplay-writer)
    
    Configuration via environment variables:
    - OPENAI_API_KEY: Your API key
    - OPENAI_BASE_URL: Custom base URL (optional)
    - LLM_MODEL: Model to use (default: gpt-4o)
    """
    
    # Available skills with their descriptions for system prompt
    AVAILABLE_SKILLS = {
        'fiction-writer': 'Specialized workflow for novel and fiction writing. Handles character arcs, plot beats, dialogue focus, scene structure, and narrative pacing.',
        'non-fiction-author': 'Specialized workflow for non-fiction book writing. Handles research citation, factual accuracy, logical structure, reader education, and authoritative tone.',
        'academic-writer': 'Specialized workflow for academic and scholarly writing. Handles formal tone, peer-review style, reference formatting, literature review integration, and methodological rigor.',
        'childrens-book-creator': 'Specialized workflow for children\'s book writing. Handles simple language, educational themes, age-appropriate content, illustration prompts, and engaging storytelling.',
        'screenplay-writer': 'Specialized workflow for screenwriting and script writing. Handles scene headings, action lines, dialogue formatting, character introductions, and visual storytelling.'
    }
    
    # Skill-specific system prompt additions
    SKILL_PROMPTS = {
        'fiction-writer': "Focus on character development arcs, plot structure (setup, rising action, climax, resolution), scene and chapter structuring, dialogue that reveals character and advances plot, pacing and tension management, and genre conventions.",
        'non-fiction-author': "Focus on research methodology and citation integration, logical argument structure and flow, reader education and knowledge transfer, authoritative yet accessible tone, fact-checking and accuracy verification, and practical application and actionable takeaways.",
        'academic-writer': "Maintain formal academic tone and terminology, integrate literature review properly, describe methods clearly with justification, follow specific citation format consistently (APA, MLA, Chicago, IEEE), and base arguments on empirical evidence or logical reasoning.",
        'childrens-book-creator': "Use age-appropriate vocabulary and sentence structure, include educational themes and moral lessons, use repetition and rhythm for engagement, provide illustration-friendly scenes, ensure safety and appropriateness of content, and create engaging storytelling with clear beginning, middle, and end.",
        'screenplay-writer': "Use standard screenplay formatting (scene headings, action lines, dialogue), focus on visual storytelling over exposition, introduce characters properly with stage directions, maintain pacing for visual medium, and ensure dialogue sounds natural when spoken."
    }

    # System prompts for different phases
    SYSTEM_PROMPTS = {
        "planning": """You are an expert book planner and outline creator. Your role is to create 
detailed, compelling book outlines that serve as the foundation for a complete novel.

When creating an outline, consider:
- Genre conventions and reader expectations
- Character development arcs
- Plot structure (setup, rising action, climax, resolution)
- Pacing and chapter distribution
- Themes and motifs

Provide structured, detailed outlines that will guide the writing process.""",

        "research": """You are a research assistant specializing in gathering background information 
for fiction writing. Your role is to provide relevant context, world-building details, and 
factual information that will make the story more authentic and engaging.

Focus on:
- Historical or cultural context relevant to the story
- Technical details that add authenticity
- Character background research
- Setting and location details
- Genre-specific conventions""",

        "writing": """You are a skilled fiction writer. Your role is to write engaging, 
well-crafted chapters that bring the story to life. 

Focus on:
- Vivid, sensory descriptions
- Natural dialogue that reveals character
- Proper pacing and scene structure
- Emotional resonance
- Consistent voice and style

Write complete, polished chapters that advance the plot while developing characters.""",

        "editing": """You are a professional book editor. Your role is to review and improve 
written content for clarity, consistency, and quality.

Focus on:
- Narrative flow and pacing
- Character consistency
- Plot coherence
- Dialogue quality
- Language and style improvements
- Grammar and punctuation"""
    }
    
    def __init__(
        self, 
        tools: List[BaseTool],
        llm_client: Optional[LLMClient] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = None,
        db: Optional[BookDatabase] = None
    ):
        """
        Initialize the BookWritingAgent.
        
        Args:
            tools: List of tools the agent can use
            llm_client: Pre-configured LLMClient (optional)
            api_key: OpenAI API key (uses env var if not provided)
            base_url: Custom base URL for OpenAI-compatible APIs
            model: Model to use (default from env or gpt-4o)
            db: BookDatabase instance (optional)
        """
        self.tools = {tool.name(): tool for tool in tools}
        self.conversation_history = {}
        self.project_states = {}
        self._state_lock = threading.RLock()
        # Per-project progress callbacks so concurrent tasks don't clobber each
        # other (the agent is a singleton shared across worker threads).
        self.progress_callbacks: Dict[str, Callable] = {}
        self.db = db or BookDatabase()

        # Agent configuration
        self.max_iterations = 20
        self.current_iteration = 0
        # Hard cap on chapters per book as a safety net (the writing loop now
        # runs until the target is met rather than being gated by max_iterations).
        self.max_chapters = 200
        # Output token budget for a single chapter. 4096 truncates ~5000-word
        # chapters mid-sentence; 8000 comfortably fits a full chapter on modern
        # models. Override per-call where the model supports more.
        self.chapter_max_tokens = 8000
        
        # Initialize LLM client
        if llm_client:
            self.llm = llm_client
        else:
            self.llm = self._create_llm_client(api_key, base_url, model)
        
        # Convert tools to definitions for function calling
        self.tool_definitions = [
            ToolDefinition(
                name=tool.name(),
                description=tool.description(),
                parameters=tool.parameters_schema()
            )
            for tool in tools
        ]
        
        logger.info(
            f"BookWritingAgent initialized with {len(self.tools)} tools, "
            f"using model: {self.llm.config.model}"
        )
        
        # Add writing-specific tools if available
        self._add_writing_tools()
        
        # Load skill descriptions for system prompt
        self.skill_descriptions = self.AVAILABLE_SKILLS
    
    def _ensure_project_state(self, project_id: str) -> bool:
        """Ensure the project state is loaded into memory."""
        if project_id in self.project_states:
            # Also ensure running summary exists
            state = self.project_states[project_id]
            if 'running_summary' not in state:
                state['running_summary'] = {
                    'chapters_summarized': 0,
                    'summary_content': '',
                    'characters_introduced': [],
                    'locations_mentioned': []
                }
            return True
            
        logger.info(f"Loading project state from database for: {project_id}")
        project = self.db.get_project(project_id)
        if not project:
            logger.error(f"Project {project_id} not found in database")
            return False
            
        # Try to load running summary from metadata if it exists
        metadata_summary = project.metadata.get('running_summary', {})
        
        self.project_states[project_id] = {
            'project': project,
            'current_phase': project.status,
            'chapter_count': project.chapters_completed,
            'total_words': project.total_words,
            'iterations': 0, # We don't track iterations across restarts yet
            'completed': project.status == 'completed',
            'errors': [],
            'conversation_history': project.metadata.get('conversation_history', []),
            'outline': project.outline or {},
            'research_materials': project.research_materials or {},
            'running_summary': metadata_summary if metadata_summary else {
                'chapters_summarized': 0,
                'summary_content': '',
                'characters_introduced': [],
                'locations_mentioned': []
            },
            'agent_activity_log': project.metadata.get('agent_activity_log', [])
        }
        return True

    def _save_project_state(self, project_id: str):
        """Save the project state to the database."""
        if project_id not in self.project_states:
            return

        with self._state_lock:
            state = self.project_states[project_id]
            project = state['project']

            # Update project object with current state
            project.status = state['current_phase']
            project.chapters_completed = state['chapter_count']
            project.total_words = state['total_words']
            project.outline = state.get('outline')
            project.research_materials = state.get('research_materials')

            # Trim conversation history to prevent unbounded growth. Keep the
            # most recent messages so the agent retains recent context without
            # the persisted payload (and future prompts) ballooning over time.
            history = state.get('conversation_history', [])
            max_history = getattr(self, 'max_conversation_history', 100)
            if len(history) > max_history:
                history = history[-max_history:]
                state['conversation_history'] = history
            project.metadata['conversation_history'] = history

            # Save running summary to metadata
            running_summary = state.get('running_summary', {})
            project.metadata['running_summary'] = running_summary

            # Trim and save agent activity log
            activity_log = state.get('agent_activity_log', [])
            max_logs = getattr(self, 'max_agent_activity_logs', 500)
            if len(activity_log) > max_logs:
                activity_log = activity_log[-max_logs:]
            project.metadata['agent_activity_log'] = activity_log

            # Persist to database
            self.db.save_project(project)
            logger.info(f"Project state saved to database for: {project_id}")

    def resume_writing_process(self, project_id: str) -> Dict[str, Any]:
        """
        Resume a writing process from where it left off.

        This method is called when restarting a project that was interrupted.
        It loads the saved state and determines which phase to resume from.
        """
        try:
            # Load project from database
            project = self.db.get_project(project_id)
            if not project:
                return {'success': False, 'error': 'Project not found'}

            logger.info(f"Resuming writing process for project: {project_id}")

            # Initialize state from saved project
            metadata_summary = project.metadata.get('running_summary', {})
            self.project_states[project_id] = {
                'project': project,
                'current_phase': project.status,
                'chapter_count': project.chapters_completed,
                'total_words': project.total_words,
                'iterations': 0,
                'completed': project.status == 'completed',
                'errors': [],
                'conversation_history': project.metadata.get('conversation_history', []),
                'outline': project.outline or {},
                'research_materials': project.research_materials or {},
                'running_summary': metadata_summary if metadata_summary else {
                    'chapters_summarized': 0,
                    'summary_content': '',
                    'characters_introduced': [],
                    'locations_mentioned': []
                },
                'agent_activity_log': project.metadata.get('agent_activity_log', [])
            }

            state = self.project_states[project_id]

            # Determine resume point based on status
            if project.status == 'completed':
                return {
                    'success': True,
                    'message': 'Project already completed',
                    'phase': 'completed'
                }

            if project.status == 'writing':
                # Resume writing from last chapter
                logger.info(f"Resuming writing from chapter {state['chapter_count'] + 1}")
                return self._run_agentic_loop(project_id, resume=True)

            elif project.status == 'editing':
                # Resume editing
                logger.info("Resuming editing phase")
                return self._run_agentic_loop(project_id, resume=True)

            else:
                # Start fresh or from planning
                logger.info(f"Starting fresh from phase: {project.status}")
                return self.start_writing_process(project)

        except Exception as e:
            logger.error(f"Error resuming writing process: {e}")
            return {
                'success': False,
                'error': str(e),
                'phase': 'resume'
            }

    def set_progress_callback(self, project_id: str, callback: Callable):
        """Set a per-project callback function to receive progress updates."""
        self.progress_callbacks[project_id] = callback

    def clear_progress_callback(self, project_id: str):
        """Remove a per-project progress callback."""
        self.progress_callbacks.pop(project_id, None)

    def _report_progress(self, project_id: str, phase: str, progress: float, message: str, activity: str = None):
        """Report progress to the project's callback if set."""
        callback = self.progress_callbacks.get(project_id)
        if callback:
            try:
                callback(phase, progress, message, activity)
            except Exception as e:
                logger.warning(f"Progress callback error for {project_id}: {e}")

    def _log_activity(self, project_id: str, phase: str, action: str, details: Dict[str, Any]):
        """Log an agent activity event."""
        if project_id not in self.project_states:
            return
        
        state = self.project_states[project_id]
        activity_log = state.get('agent_activity_log', [])
        
        log_entry = AgentActivityLog(phase=phase, action=action, details=details).to_dict()
        activity_log.append(log_entry)
        
        # Keep only the most recent logs
        max_logs = getattr(self, 'max_agent_activity_logs', 500)
        if len(activity_log) > max_logs:
            activity_log = activity_log[-max_logs:]
        
        state['agent_activity_log'] = activity_log

    def _add_writing_tools(self):
        """Add writing-specific tools to the agent's toolset."""
        try:
            from tools.writing_tools import (
                RunningSummaryTool,
                ChapterEvaluationTool,
                CharacterConsistencyTool
            )
            # Add running summary tool if not already present
            if 'running_summary' not in self.tools:
                self.tools['running_summary'] = RunningSummaryTool()
                # Add to tool definitions
                self.tool_definitions.append(ToolDefinition(
                    name='running_summary',
                    description=RunningSummaryTool().description(),
                    parameters=RunningSummaryTool().parameters_schema()
                ))
            if 'evaluate_chapter' not in self.tools:
                self.tools['evaluate_chapter'] = ChapterEvaluationTool()
                self.tool_definitions.append(ToolDefinition(
                    name='evaluate_chapter',
                    description=ChapterEvaluationTool().description(),
                    parameters=ChapterEvaluationTool().parameters_schema()
                ))
            if 'character_consistency' not in self.tools:
                self.tools['character_consistency'] = CharacterConsistencyTool()
                self.tool_definitions.append(ToolDefinition(
                    name='character_consistency',
                    description=CharacterConsistencyTool().description(),
                    parameters=CharacterConsistencyTool().parameters_schema()
                ))
            logger.info("Added writing-specific tools to agent")
        except ImportError as e:
            logger.warning(f"Could not load writing-specific tools: {e}")

    def _load_skill_content(self, skill_name: str) -> Optional[str]:
        """
        Load the full SKILL.md content for a domain-specific skill.
        
        Uses progressive disclosure pattern: metadata is in system prompt,
        full content is loaded on-demand when skill is selected.
        """
        try:
            # Try to load from .agents/skills directory
            skill_dir = os.path.join(os.path.dirname(__file__), '..', '.agents', 'skills', skill_name)
            if not os.path.exists(skill_dir):
                # Try relative path from current working directory
                skill_dir = os.path.join('.agents', 'skills', skill_name)
            
            skill_md_path = os.path.join(skill_dir, 'SKILL.md')
            if os.path.exists(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not load skill content for {skill_name}: {e}")
        
        return None

    def _get_skill_guidance(self, project: Any) -> str:
        """
        Get skill-specific guidance based on the project's selected skill.
        
        Returns a string of guidance to include in system prompts.
        """
        skill = getattr(project, 'skill', None) or self.AVAILABLE_SKILLS.get('fiction-writer')
        
        # Return skill-specific prompt additions
        if skill in self.SKILL_PROMPTS:
            guidance = "\n\nSkill Guidance ({}):\n{}".format(skill, self.SKILL_PROMPTS[skill])
            return guidance
        elif skill == 'fiction':
            return "\n\nSkill Guidance (fiction-writer):\n" + self.SKILL_PROMPTS['fiction-writer']
        elif skill in ['non_fiction', 'business', 'guide']:
            return "\n\nSkill Guidance (non-fiction-author):\n" + self.SKILL_PROMPTS['non-fiction-author']
        elif skill in ['academic', 'research', 'textbook']:
            return "\n\nSkill Guidance (academic-writer):\n" + self.SKILL_PROMPTS['academic-writer']
        elif skill in ['children', 'kids', 'picture-book']:
            return "\n\nSkill Guidance (childrens-book-creator):\n" + self.SKILL_PROMPTS['childrens-book-creator']
        elif skill in ['screenplay', 'script', 'film', 'tv']:
            return "\n\nSkill Guidance (screenplay-writer):\n" + self.SKILL_PROMPTS['screenplay-writer']
        
        # Default guidance
        return "\n\nGeneral Writing Guidance:\nFocus on engaging content, proper structure, and consistent quality throughout."

    def _update_running_summary(self, project_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Update the running story summary with the latest chapter."""
        if 'running_summary' not in state:
            state['running_summary'] = {
                'chapters_summarized': 0,
                'summary_content': '',
                'characters_introduced': [],
                'locations_mentioned': []
            }
        
        summary_state = state['running_summary']
        chapter_count = state['chapter_count']
        project = state['project']
        
        # If we just completed a chapter, update the running summary
        if chapter_count > summary_state.get('chapters_summarized', 0):
            try:
                # Read the latest chapter to summarize
                read_tool = self.tools.get('read_file')
                if read_tool:
                    chapter_result = read_tool.execute(
                        project_id=project_id,
                        path=f"chapters/chapter_{chapter_count}.md"
                    )
                    
                    if isinstance(chapter_result, dict) and chapter_result.get('success'):
                        chapter_content = chapter_result.get('content', '')
                    elif isinstance(chapter_result, str):
                        chapter_content = chapter_result
                    else:
                        chapter_content = ''
                else:
                    chapter_content = ''
                
                # Generate summary using LLM if we have chapter content and it's the first time summarizing this chapter
                if chapter_content and not summary_state.get('summary_content'):
                    summary_prompt = f"""Provide a concise running summary of the story so far for the book "{project.title}".

Current chapters completed: {chapter_count}
Latest chapter content (Chapter {chapter_count}):
{chapter_content[:3000]}...

Please provide:
1. A brief 2-3 sentence summary of what happened in this chapter and overall story progress
2. Any new characters introduced
3. Any new locations or settings mentioned

Format your response as:
SUMMARY: [brief story summary]
CHARACTERS: [comma-separated list of characters]
LOCATIONS: [comma-separated list of locations]"""
                    
                    messages = [
                        {"role": "system", "content": "You are a story continuity assistant. Provide concise, accurate summaries."},
                        {"role": "user", "content": summary_prompt}
                    ]
                    
                    try:
                        response = self.llm.chat(messages, max_tokens=500)
                        if response and hasattr(response, 'content') and response.content:
                            content = response.content
                            # Parse the response
                            summary_line = ""
                            characters_list = []
                            locations_list = []
                            
                            for line in content.split('\n'):
                                if line.startswith('SUMMARY:'):
                                    summary_line = line.replace('SUMMARY:', '').strip()
                                elif line.startswith('CHARACTERS:'):
                                    chars = line.replace('CHARACTERS:', '').strip()
                                    characters_list = [c.strip() for c in chars.split(',') if c.strip()]
                                elif line.startswith('LOCATIONS:'):
                                    locs = line.replace('LOCATIONS:', '').strip()
                                    locations_list = [l.strip() for l in locs.split(',') if l.strip()]
                            
                            summary_state['summary_content'] = summary_line
                            summary_state['characters_introduced'] = characters_list
                            summary_state['locations_mentioned'] = locations_list
                            summary_state['chapters_summarized'] = chapter_count
                    except Exception as e:
                        logger.warning(f"Failed to generate running summary: {e}")
            except Exception as e:
                logger.warning(f"Error updating running summary: {e}")
        
        return state.get('running_summary', {})

    def generate_story_arc_visualization(self, project_id: str) -> Dict[str, Any]:
        """
        Generate a story arc/timeline visualization based on completed chapters.
        
        Returns:
            Dict with story arc data and HTML representation
        """
        try:
            state = self.project_states.get(project_id, {})
            project = state.get('project') if state else None
            
            if not project:
                return {'success': False, 'error': 'Project not found'}
            
            chapter_count = state.get('chapter_count', 0)
            running_summary = state.get('running_summary', {})
            
            # Generate story arc data structure
            story_arc = {
                'phases': [
                    {'name': 'Setup', 'chapters': '1-25%', 'description': 'Introduce protagonist, world, and inciting incident'},
                    {'name': 'Rising Action', 'chapters': '25%-75%', 'description': 'Build tension, introduce obstacles, develop relationships'},
                    {'name': 'Climax', 'chapters': '75%-90%', 'description': 'Peak conflict, protagonist faces main challenge'},
                    {'name': 'Resolution', 'chapters': '90%-100%', 'description': 'Consequences, character growth, new status quo'}
                ],
                'current_phase': self._determine_current_phase(chapter_count),
                'characters_introduced': running_summary.get('characters_introduced', []),
                'locations_mentioned': running_summary.get('locations_mentioned', [])
            }
            
            # Generate HTML visualization
            html_visualization = "<div class='story-arc-viz'>"
            html_visualization += f"<h3>Story Arc Timeline - {project.title}</h3>"
            html_visualization += '<div class="timeline-container">'
            
            for phase in story_arc['phases']:
                is_current = phase['name'].lower() == story_arc['current_phase'].lower()
                status_class = 'current' if is_current else 'upcoming'
                if is_current:
                    status_class = 'active'
                
                html_visualization += f'''
                    <div class="timeline-phase {status_class}">
                        <div class="phase-header">
                            <span class="phase-name">{phase['name']}</span>
                            <span class="phase-chapters">{phase['chapters']}</span>
                        </div>
                        <div class="phase-description">{phase['description']}</div>
                    </div>
                '''
            
            html_visualization += '</div>'
            html_visualization += '<div class="story-elements">'
            if story_arc.get('characters_introduced'):
                chars_list = '</li><li>'.join(story_arc['characters_introduced'])
                html_visualization += '<div class="characters-section"><h4>Characters Introduced: {}</h4><ul><li>{}</li></ul></div>'.format(len(story_arc['characters_introduced']), chars_list)
            if story_arc.get('locations_mentioned'):
                locs_list = '</li><li>'.join(story_arc['locations_mentioned'])
                html_visualization += '<div class="locations-section"><h4>Locations Mentioned: {}</h4><ul><li>{}</li></ul></div>'.format(len(story_arc['locations_mentioned']), locs_list)
            html_visualization += '</div></div>'
            
            return {
                'success': True,
                'story_arc': story_arc,
                'html_visualization': html_visualization,
                'chapters_completed': chapter_count
            }
        except Exception as e:
            logger.error(f"Error generating story arc visualization: {e}")
            return {'success': False, 'error': str(e)}

    def _determine_current_phase(self, chapter_count: int) -> str:
        """Determine the current story phase based on chapter count."""
        # This is a simplified determination - would be more sophisticated in production
        if chapter_count <= 2:
            return 'setup'
        elif chapter_count <= 6:
            return 'rising_action'
        elif chapter_count <= 8:
            return 'climax'
        else:
            return 'resolution'

    def generate_version_diff(self, project_id: str, version1_num: int, version2_num: int) -> Dict[str, Any]:
        """
        Generate a visual diff between two chapter versions.
        
        Args:
            project_id: The project identifier
            version1_num: First version number to compare
            version2_num: Second version number to compare
            
        Returns:
            Dict with diff information and HTML representation
        """
        try:
            # Get chapter versions from database or state
            # For now, we'll generate a unified diff format
            state = self.project_states.get(project_id, {})
            project = state.get('project') if state else None
            
            if not project:
                return {'success': False, 'error': 'Project not found'}
            
            # Generate diff using difflib
            import difflib
            
            # Get version contents (simplified for now - would get from version_model)
            # In a real implementation, this would fetch actual version content from database
            v1_content = f"// Version {version1_num} content placeholder"
            v2_content = f"// Version {version2_num} content placeholder"
            
            # Generate unified diff
            d = difflib.unified_diff(
                v1_content.splitlines(keepends=True),
                v2_content.splitlines(keepends=True),
                fromfile=f'chapter_v{version1_num}',
                tofile=f'chapter_v{version2_num}',
                lineterm=''
            )
            
            diff_lines = list(d)
            added = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
            modified = sum(1 for line in diff_lines if line.startswith('@'))
            
            # Generate HTML diff representation
            html_diff = "<div class='diff-view'>"
            html_diff += f"<h4>Version {version1_num} → Version {version2_num}</h4>"
            html_diff += f"<p>Adds: {added}, Removes: {removed}, Modifies: {modified}</p>"
            html_diff += "<pre class='unified-diff'>"
            for line in diff_lines:
                if line.startswith('+'):
                    html_diff += f"<span class='diff-added'>{line}</span>"
                elif line.startswith('-'):
                    html_diff += f"<span class='diff-removed'>{line}</span>"
                elif line.startswith('@'):
                    html_diff += f"<span class='diff-context'>{line}</span>"
                else:
                    html_diff += f"<span class='diff-context'>{line}</span>"
            html_diff += "</pre></div>"
            
            return {
                'success': True,
                'version1': version1_num,
                'version2': version2_num,
                'added_lines': added,
                'removed_lines': removed,
                'modified_lines': modified,
                'diff_html': html_diff,
                'changes_summary': f"Added {added} lines, removed {removed} lines"
            }
        except Exception as e:
            logger.error(f"Error generating version diff: {e}")
            return {'success': False, 'error': str(e)}

    def _perform_cross_chapter_consistency_check(self, project_id: str, state: Dict[str, Any]):
        """
        Perform cross-chapter consistency checks using grep_search before editing.
        
        This helps identify potential inconsistencies in character names, locations,
        and terminology across the entire manuscript.
        """
        try:
            grep_tool = self.tools.get('grep_search')
            if not grep_tool:
                logger.warning("grep_search tool not available for cross-chapter consistency check")
                return
            
            # Extract character and location names from running summary or outline
            running_summary = state.get('running_summary', {})
            characters_to_check = running_summary.get('characters_introduced', [])
            locations_to_check = running_summary.get('locations_mentioned', [])
            
            consistency_notes = []
            
            # Check character name consistency
            if characters_to_check:
                for char_name in characters_to_check[:5]:  # Limit to first 5 characters
                    try:
                        result = grep_tool.execute(
                            project_id=project_id,
                            query=char_name,
                            path=".",
                            file_pattern="chapters/*.md",
                            ignore_case=True
                        )
                        
                        if isinstance(result, dict) and result.get('success'):
                            matches = result.get('matches', [])
                            if len(matches) > 0:
                                consistency_notes.append(f"Character '{char_name}' mentioned in {len(matches)} chapters")
                    except Exception as e:
                        logger.warning(f"Consistency check for character '{char_name}': {e}")
            
            # Check location consistency
            if locations_to_check:
                for loc_name in locations_to_check[:3]:  # Limit to first 3 locations
                    try:
                        result = grep_tool.execute(
                            project_id=project_id,
                            query=loc_name,
                            path=".",
                            file_pattern="chapters/*.md",
                            ignore_case=True
                        )
                        
                        if isinstance(result, dict) and result.get('success'):
                            matches = result.get('matches', [])
                            if len(matches) > 0:
                                consistency_notes.append(f"Location '{loc_name}' mentioned in {len(matches)} chapters")
                    except Exception as e:
                        logger.warning(f"Consistency check for location '{loc_name}': {e}")
            
            # Log the consistency check results
            if consistency_notes:
                logger.info(f"Cross-chapter consistency notes: {'; '.join(consistency_notes)}")
                state['consistency_notes'] = consistency_notes
                
        except Exception as e:
            logger.warning(f"Error in cross-chapter consistency check: {e}")

    def _create_llm_client(
        self, 
        api_key: Optional[str], 
        base_url: Optional[str],
        model: Optional[str]
    ) -> LLMClient:
        """Create the LLM client based on configuration."""
        
        # Get configuration from environment or parameters
        api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
        model = model or os.getenv("LLM_MODEL", "gpt-4o")
        
        # Create appropriate client based on configuration
        if base_url:
            logger.info(f"Using custom base URL: {base_url}")
            return LLMClient(
                api_key=api_key or "not-needed",
                base_url=base_url,
                model=model,
                temperature=0.7,
                max_tokens=4096
            )
        elif api_key:
            logger.info("Using OpenAI API")
            return LLMClient(
                api_key=api_key,
                model=model,
                temperature=0.7,
                max_tokens=4096
            )
        else:
            # Default to local server if no API key
            logger.warning("No API key found, attempting local server connection")
            return create_local_client(
                base_url="http://localhost:1234/v1",
                model=model or "local-model"
            )
    
    def start_writing_process(self, project) -> Dict[str, Any]:
        """Start the agentic book writing process."""
        try:
            project_id = project.id
            logger.info(f"Starting book writing process for project: {project_id}")
            
            # Initialize project state
            self.project_states[project_id] = {
                'project': project,
                'current_phase': 'planning',
                'chapter_count': 0,
                'total_words': 0,
                'iterations': 0,
                'completed': False,
                'errors': [],
                'conversation_history': []
            }
            
            # Start the agentic loop
            result = self._run_agentic_loop(project_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in start_writing_process: {e}")
            return {
                'success': False,
                'error': str(e),
                'phase': 'initialization'
            }
    
    def _run_agentic_loop(self, project_id: str, resume: bool = False) -> Dict[str, Any]:
        """Main agentic loop that handles the book writing process.

        Args:
            project_id: The project identifier.
            resume: If True, continue from the current phase without
                re-initializing earlier phases (used when resuming a
                paused/interrupted writing or editing process).
        """

        state = self.project_states[project_id]
        project = state['project']

        try:
            # Phase 1: Planning and Outline Generation
            if state['current_phase'] == 'planning':
                logger.info("Phase 1: Planning and Outline Generation")
                self._report_progress(project_id, 'planning', 10.0, 'Creating book outline and structure...', 'Starting planning phase')
                self._log_activity(project_id, 'planning', 'starting_planning', {'message': 'Beginning outline generation'})

                planning_result = self._execute_planning_phase(project_id)

                if planning_result['success']:
                    state['outline'] = planning_result.get('outline', {})
                    state['current_phase'] = 'research'
                    self._report_progress(project_id, 'planning', 100.0, 'Planning completed successfully', 'Outline created successfully')
                    logger.info("Outline created successfully, moving to research phase")
                    self._log_activity(project_id, 'planning', 'completed_planning', {'outline_length': len(str(planning_result.get('content', '')))})
                    self._save_project_state(project_id)
                else:
                    state['errors'].append(f"Planning failed: {planning_result.get('error')}")
                    self._log_activity(project_id, 'planning', 'failed_planning', {'error': planning_result.get('error')})
                    self._save_project_state(project_id)
                    return planning_result

            # Phase 2: Research and Background
            if state['current_phase'] == 'research':
                logger.info("Phase 2: Research and Background")
                self._report_progress(project_id, 'research', 30.0, 'Gathering background information...', 'Starting research phase')
                self._log_activity(project_id, 'research', 'starting_research', {'message': 'Beginning background research'})

                research_result = self._execute_research_phase(project_id, state['outline'])

                if research_result['success']:
                    state['research_materials'] = research_result.get('materials', {})
                    state['current_phase'] = 'writing'
                    self._report_progress(project_id, 'research', 100.0, 'Research completed successfully', 'Research phase completed')
                    logger.info("Research completed, moving to writing phase")
                    self._log_activity(project_id, 'research', 'completed_research', {'materials_length': len(str(research_result.get('content', '')))})
                    self._save_project_state(project_id)
                else:
                    state['errors'].append(f"Research failed: {research_result.get('error')}")
                    self._log_activity(project_id, 'research', 'failed_research', {'error': research_result.get('error')})
                    self._save_project_state(project_id)
                    return research_result

            # Phase 3: Chapter Writing Loop
            # Decoupled from max_iterations so the iteration cap (meant to bound
            # per-chapter agentic editing loops) cannot cut a long book short.
            # A generous chapter cap prevents runaway generation.
            while state['current_phase'] == 'writing':
                if state['chapter_count'] >= self.max_chapters:
                    logger.warning(f"Reached chapter safety cap ({self.max_chapters}), stopping writing phase")
                    break
                
                chapter_num = state['chapter_count'] + 1
                logger.info(f"Phase 3: Writing Chapter {chapter_num}")
                self._log_activity(project_id, 'writing', f'starting_chapter_{chapter_num}', {'chapter_number': chapter_num})
                
                # Update running summary if we have previous chapters
                state['running_summary'] = self._update_running_summary(project_id, state)
                
                chapter_result = self._write_chapter_with_llm(project_id, update_summary=False)
                
                if chapter_result['success']:
                    state['chapter_count'] += 1
                    state['total_words'] += chapter_result.get('words_written', 0)
                    state['iterations'] += 1
                    
                    # Update running summary after successful chapter write
                    self._update_running_summary(project_id, state)
                    
                    if self._is_book_complete(project_id):
                        state['current_phase'] = 'editing'
                        logger.info("All chapters written, moving to editing phase")
                    
                    self._log_activity(project_id, 'writing', f'completed_chapter_{chapter_num}', {
                        'words_written': chapter_result.get('words_written', 0),
                        'chapters_total': state['chapter_count']
                    })
                    self._save_project_state(project_id)
                    
                    if state['current_phase'] == 'editing':
                        break
                else:
                    state['errors'].append(f"Chapter writing failed: {chapter_result.get('error')}")
                    self._log_activity(project_id, 'writing', f'failed_chapter_{chapter_num}', {'error': chapter_result.get('error')})
                    self._save_project_state(project_id)
                    return chapter_result
            
            # Phase 4: Editing and Refinement
            if state['current_phase'] == 'editing':
                logger.info("Phase 4: Editing and Refinement")
                self._log_activity(project_id, 'editing', 'starting_editing', {'chapters_to_edit': state['chapter_count']})
                
                edit_result = self._execute_editing_phase(project_id)
                
                if edit_result['success']:
                    state['current_phase'] = 'refining'
                    state['completed'] = True
                    logger.info("Editing completed successfully, entering Agent Mode")
                    self._log_activity(project_id, 'editing', 'completed_editing', {
                        'chapters_edited': edit_result.get('chapters_edited', 0),
                        'total_tool_calls': edit_result.get('total_tool_calls', 0)
                    })
                    self._save_project_state(project_id)
                else:
                    state['errors'].append(f"Editing failed: {edit_result.get('error')}")
                    self._log_activity(project_id, 'editing', 'failed_editing', {'error': edit_result.get('error')})
                    self._save_project_state(project_id)
                    return edit_result
            
            return {
                'success': True,
                'phase': state['current_phase'],
                'iterations': state['iterations'],
                'chapters_completed': state['chapter_count'],
                'total_words': state['total_words'],
                'completed': state['completed']
            }
                
        except Exception as e:
            logger.error(f"Error in agentic loop: {e}")
            state['errors'].append(str(e))
            return {
                'success': False,
                'error': str(e),
                'phase': state['current_phase'],
                'iterations': state['iterations']
            }
    
    @retry_with_backoff(max_retries=2, base_delay=2.0, max_delay=30.0)
    def _execute_planning_phase(self, project_id: str) -> Dict[str, Any]:
        """Execute the planning phase using LLM."""
        state = self.project_states[project_id]
        project = state['project']
        
        try:
            logger.info(f"Starting planning phase for project: {project.title}")
            
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPTS["planning"] + self._get_skill_guidance(project)},
                {"role": "user", "content": f"""Create a detailed outline for a book with the following specifications:

Title: {project.title}
Genre: {project.genre}
Target Length: {project.target_length:,} words
Writing Style: {project.writing_style}

Please create a comprehensive outline including:
1. Overall story premise and themes
2. Main characters with brief descriptions
3. Chapter-by-chapter breakdown (aim for {project.target_length // 5000} chapters)
4. Key plot points and story beats
5. Character arcs and development

Format the outline in a structured way that can guide the writing process."""}
            ]
            
            logger.info("Making LLM call for planning phase")
            response = self.llm.chat(messages, max_tokens=4096)
            logger.info(f"LLM response type: {type(response)}")
            
            if response and hasattr(response, 'content') and response.content:
                logger.info(f"LLM content length: {len(response.content)} characters")
                logger.info(f"LLM content preview: {response.content[:200]}...")
                
                # Parse the outline from the response
                outline = {
                    'raw_content': response.content,
                    'chapters': self._parse_chapter_outline(response.content, project.target_length // 5000),
                    'created_at': datetime.now().isoformat()
                }
                
                # Save outline using write_file tool if available
                if 'write_file' in self.tools:
                    try:
                        self.tools['write_file'].execute(
                            project_id=project_id,
                            path="outline.md",
                            content=response.content
                        )
                        logger.info("Outline saved successfully")
                    except Exception as save_error:
                        logger.error(f"Failed to save outline: {save_error}")
                
                logger.info("Planning phase completed successfully")
                return {
                    'success': True,
                    'outline': outline,
                    'content': response.content
                }
            else:
                logger.error(f"Invalid LLM response: {response}")
                return {
                    'success': False,
                    'error': 'No content generated for outline'
                }
        except Exception as e:
            logger.error(f"Error in planning phase: {e}")
            import traceback
            logger.error(f"Planning phase traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Planning phase failed: {str(e)}'
            }
    
    def _execute_research_phase(self, project_id: str, outline: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the research phase using LLM."""
        state = self.project_states[project_id]
        project = state['project']
        
        try:
            logger.info(f"Starting research phase for project: {project.title}")
            
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPTS["research"] + self._get_skill_guidance(project)},
                {"role": "user", "content": f"""Based on the following book outline, provide research notes and background information:

Title: {project.title}
Genre: {project.genre}

Outline:
{outline.get('raw_content', 'No outline available')}

Please provide:
1. World-building details relevant to the story
2. Character background research
3. Setting descriptions and atmosphere notes
4. Any technical or historical details needed
5. Genre-specific elements to include

This research will inform the writing process."""}
            ]
            
            logger.info("Making LLM call for research phase")
            response = self.llm.chat(messages, max_tokens=3000)
            
            if response and hasattr(response, 'content') and response.content:
                logger.info(f"Research content length: {len(response.content)} characters")
                
                materials = {
                    'raw_content': response.content,
                    'created_at': datetime.now().isoformat()
                }
                
                # Save research using write_file tool if available
                if 'write_file' in self.tools:
                    try:
                        self.tools['write_file'].execute(
                            project_id=project_id,
                            path="research_notes.md",
                            content=response.content
                        )
                        logger.info("Research notes saved successfully")
                    except Exception as save_error:
                        logger.error(f"Failed to save research notes: {save_error}")
                
                logger.info("Research phase completed successfully")
                return {
                    'success': True,
                    'materials': materials,
                    'content': response.content
                }
            else:
                logger.error(f"Invalid research LLM response: {response}")
                return {
                    'success': False,
                    'error': 'No content generated for research'
                }
        except Exception as e:
            logger.error(f"Error in research phase: {e}")
            import traceback
            logger.error(f"Research phase traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Research phase failed: {str(e)}'
            }
    
    def _execute_writing_phase(self, project_id: str, outline: Dict[str, Any], research: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the writing phase using LLM."""
        state = self.project_states[project_id]
        project = state['project']
        
        try:
            logger.info(f"Starting writing phase for project: {project.title}")
            
            chapters = outline.get('chapters', [])
            if not chapters:
                logger.error("No chapters found in outline")
                return {'success': False, 'error': 'No chapters found in outline'}
            
            # Write each chapter
            written_chapters = []
            for i, chapter in enumerate(chapters):
                logger.info(f"Writing chapter {i+1}/{len(chapters)}: {chapter.get('title', 'Untitled')}")
                
                self._report_progress(project_id, 'writing', 30.0 + (i / len(chapters)) * 60.0,
                                    f'Writing chapter {i+1}: {chapter.get("title", "Untitled")}',
                                    f'Working on chapter {i+1}')
                
                chapter_content = self._write_chapter(project_id, chapter, outline, research, i+1)
                
                if chapter_content:
                    written_chapters.append({
                        'chapter_number': i+1,
                        'title': chapter.get('title', 'Untitled'),
                        'content': chapter_content,
                        'word_count': len(chapter_content.split())
                    })
                else:
                    logger.error(f"Failed to write chapter {i+1}")
            
            logger.info(f"Writing phase completed. Wrote {len(written_chapters)} chapters.")
            return {
                'success': True,
                'chapters': written_chapters,
                'total_words': sum(ch['word_count'] for ch in written_chapters)
            }
            
        except Exception as e:
            logger.error(f"Error in writing phase: {e}")
            import traceback
            logger.error(f"Writing phase traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f'Writing phase failed: {str(e)}'
            }
    
    def _read_previous_chapter(self, project_id: str, chapter_number: int) -> Optional[str]:
        """Read a previously written chapter from the project files.

        Returns the chapter content (markdown) or None if it cannot be read.
        """
        try:
            read_tool = self.tools.get('read_file')
            if not read_tool:
                return None
            result = read_tool.execute(
                project_id=project_id,
                path=f"chapters/chapter_{chapter_number}.md"
            )
            if isinstance(result, dict) and result.get('success'):
                return result.get('content')
            if isinstance(result, str):
                return result
            return None
        except Exception as e:
            logger.warning(f"Could not read previous chapter {chapter_number} for {project_id}: {e}")
            return None

    def _write_chapter_with_llm(self, project_id: str, update_summary: bool = True) -> Dict[str, Any]:
        """
        Write a chapter using the LLM with adaptive retry strategies and partial recovery.
        
        Args:
            project_id: The project identifier
            update_summary: Whether to update the running summary after successful write
        """
        state = self.project_states[project_id]
        project = state['project']
        chapter_number = state['chapter_count'] + 1
        outline = state.get('outline', {})
        research = state.get('research_materials', {})
        
        # Adaptive retry configuration
        max_adaptive_retries = 3
        adaptive_attempts = 0
        
        while adaptive_attempts < max_adaptive_retries:
            try:
                # Get chapter-specific guidance from outline
                chapters = outline.get('chapters', [])
                chapter_guidance = ""
                total_expected_chapters = len(chapters) if chapters else max(1, project.target_length // 5000)

                # Report progress
                progress = 30.0 + (min(chapter_number - 1, total_expected_chapters) / total_expected_chapters) * 60.0
                self._report_progress(project_id, 'writing', progress, f'Writing chapter {chapter_number} of {total_expected_chapters}...', f'Writing: {project.title} - Chapter {chapter_number}')

                if chapter_number <= len(chapters):
                    chapter_info = chapters[chapter_number - 1]
                    chapter_guidance = f"\nChapter {chapter_number} should cover: {chapter_info.get('summary', 'Continue the story')}"

                # Build context from the actual previous chapter so the LLM keeps
                # continuity in tone, characters, and plot across chapter boundaries.
                previous_context = ""
                if chapter_number > 1:
                    prev_content = self._read_previous_chapter(project_id, chapter_number - 1)
                    if prev_content:
                        # Keep only the tail (ending) to bound prompt size while still
                        # giving the model the immediate lead-in to continue from.
                        prev_tail = prev_content[-3000:]
                        previous_context = (
                            f"\n\nPrevious chapter (Chapter {chapter_number - 1}) ending:\n"
                            f"{prev_tail}\n\nContinue seamlessly from where this left off, "
                            f"maintaining the established voice, characters, and plot."
                        )
                    else:
                        previous_context = "\n\nPrevious chapter summaries are available in the outline."

                messages = [
                    {"role": "system", "content": self.SYSTEM_PROMPTS["writing"] + self._get_skill_guidance(project)},
                    {"role": "user", "content": f"""Write Chapter {chapter_number} for the book "{project.title}".

Genre: {project.genre}
Writing Style: {project.writing_style}
Target chapter length: approximately {project.target_length // (project.target_length // 5000):,} words
{chapter_guidance}
{previous_context}

Book Outline Summary:
{outline.get('raw_content', 'No outline available')[:2000]}...

Research Notes:
{research.get('raw_content', 'No research available')[:1000]}...

Write a complete, engaging chapter that:
1. Advances the plot appropriately
2. Develops characters naturally
3. Maintains consistent voice and style
4. Includes vivid descriptions and natural dialogue
5. Ends with appropriate tension or resolution for this point in the story

Begin the chapter now:"""}
                ]

                response = self.llm.chat(messages, max_tokens=self.chapter_max_tokens)
                
                if response.content:
                    chapter_content = response.content
                    word_count = len(chapter_content.split())
                    
                    # Check if response is truncated (partial chapter recovery)
                    if len(response.content) < 500 and adaptive_attempts > 0:
                        logger.warning(f"Chapter {chapter_number} content seems truncated: {len(response.content)} chars")
                        adaptive_attempts += 1
                        continue
                    
                    # Save chapter using write_file tool
                    if 'write_file' in self.tools:
                        self.tools['write_file'].execute(
                            project_id=project_id,
                            path=f"chapters/chapter_{chapter_number}.md",
                            content=chapter_content
                        )
                    
                    return {
                        'success': True,
                        'chapter_number': chapter_number,
                        'words_written': word_count,
                        'chapter_title': f'Chapter {chapter_number}',
                        'content': chapter_content
                    }
                else:
                    adaptive_attempts += 1
                    if adaptive_attempts < max_adaptive_retries:
                        logger.warning(f"No content generated for chapter {chapter_number}, attempt {adaptive_attempts}/{max_adaptive_retries}. Trying with adjusted parameters...")
                        # Adjust parameters for next attempt
                        self.chapter_max_tokens = max(2048, self.chapter_max_tokens - 1000)
                        continue
                    else:
                        return {
                            'success': False,
                            'error': f'No content generated for chapter {chapter_number} after {max_adaptive_retries} attempts'
                        }
            
            except Exception as e:
                adaptive_attempts += 1
                if adaptive_attempts < max_adaptive_retries:
                    logger.warning(f"Chapter writing error on attempt {adaptive_attempts}/{max_adaptive_retries}: {e}. Retrying with fallback strategy...")
                    # Try fallback: reduce tokens and simplify prompt
                    try:
                        self.chapter_max_tokens = max(2048, self.chapter_max_tokens - 1000)
                        messages_simple = [
                            {"role": "system", "content": "Write a chapter for a fiction book. Keep it engaging and well-structured."},
                            {"role": "user", "content": f"Write Chapter {chapter_number} for the book '{project.title}'. Genre: {project.genre}. Writing Style: {project.writing_style}. Continue the story."}
                        ]
                        response = self.llm.chat(messages_simple, max_tokens=self.chapter_max_tokens)
                        if response and hasattr(response, 'content') and response.content:
                            chapter_content = response.content
                            word_count = len(chapter_content.split())
                            
                            if 'write_file' in self.tools:
                                self.tools['write_file'].execute(
                                    project_id=project_id,
                                    path=f"chapters/chapter_{chapter_number}.md",
                                    content=chapter_content
                                )
                            
                            return {
                                'success': True,
                                'chapter_number': chapter_number,
                                'words_written': word_count,
                                'chapter_title': f'Chapter {chapter_number}',
                                'content': chapter_content,
                                'fallback_strategy_used': True
                            }
                    except Exception as fallback_e:
                        logger.error(f"Fallback strategy also failed: {fallback_e}")
                
                logger.error(f"All adaptive retry attempts failed for chapter {chapter_number}: {e}")
                return {'success': False, 'error': str(e)}
    
    def _execute_editing_phase(self, project_id: str) -> Dict[str, Any]:
        """
        Execute the editing phase using an agentic approach.
        
        Like a coding agent for code, this agent reads chapters and makes targeted edits
        using the edit_file tool. It reads full chapters, identifies issues, and makes
        precise corrections without rewriting entire chapters unnecessarily.
        """
        state = self.project_states[project_id]
        project = state['project']
        
        editing_changes = []
        
        try:
            logger.info(f"Starting agentic editing for project: {project.title}")
            
            # System prompt for the editing agent - framed like a coding agent for books
            editing_system_message = f"""You are a professional book editor working like a coding agent (similar to Cursor, Windsurf, or Aider), but for book manuscripts.

Project Context:
- Title: "{project.title}"
- Genre: {project.genre}
- Total Chapters: {state['chapter_count']}
- Total Words: {state['total_words']:,}

Your Mission:
Review and improve the book manuscript using a targeted, agentic approach. Like coding agents for code, you should:

1. **Read files thoroughly**: Use read_file to examine full chapters, not just excerpts
2. **Make targeted edits**: Use edit_file for precise corrections (grammar, word choice, sentence structure)
3. **Search intelligently**: Use grep_search to find patterns across chapters (names, dates, terminology)
4. **Rewrite strategically**: Only use write_file for complete chapter rewrites when absolutely necessary

Editing Priorities:
- Grammar, spelling, punctuation errors
- Inconsistent character names, locations, or facts
- Awkward phrasing and word choice
- Pacing issues (slow scenes, rushed developments)
- Dialogue quality
- Narrative flow and transitions

Tool Usage Guidelines:
- **read_file**: Read entire chapters with line numbers to understand context
- **edit_file**: Make targeted changes by searching for exact text and replacing it
  - Use specific, unique search terms to avoid accidental replacements
  - Include surrounding context in search strings when possible
  - Can use regex for pattern matching if helpful
- **grep_search**: Find patterns across multiple chapters to check consistency
- **write_file**: Only use when a chapter needs complete rewriting

Process:
For each chapter:
1. Read the full chapter with read_file
2. Identify specific issues that need fixing
3. Use edit_file to make targeted corrections (2-10 edits per iteration is good)
4. If major structural issues exist, consider rewriting with write_file
5. Document what you changed in your response

Always include "project_id": "{project_id}" in every tool call.

Start by reading chapter 1 and begin editing it."""

            # Perform cross-chapter consistency check before editing
            self._perform_cross_chapter_consistency_check(project_id, state)
            
            # Iterate through each chapter and use AgentMode to edit it
            for chapter_num in range(1, state['chapter_count'] + 1):
                logger.info(f"Editing chapter {chapter_num} of {state['chapter_count']}")
                
                # Update progress
                progress = 30 + ((chapter_num - 1) / state['chapter_count']) * 60
                self._report_progress(project_id, 'editing', progress, f'Editing chapter {chapter_num}...', f'Processing chapter {chapter_num}/{state["chapter_count"]}')
                
                # Get running summary for context if available
                running_summary = state.get('running_summary', {})
                summary_context = ""
                if running_summary.get('summary_content'):
                    summary_context = f"\n\nRunning Story Summary:\n{running_summary['summary_content']}"
                    if running_summary.get('characters_introduced'):
                        summary_context += f"\nCharacters introduced so far: {', '.join(running_summary['characters_introduced'])}"
                    if running_summary.get('locations_mentioned'):
                        summary_context += f"\nLocations mentioned so far: {', '.join(running_summary['locations_mentioned'])}"
                
                # Initial message to start editing this chapter
                edit_message = f"""Review and edit chapter {chapter_num}.

Read the full chapter file at chapters/chapter_{chapter_num}.md, then:

1. Identify grammar, punctuation, and spelling errors
2. Check for awkward phrasing or word repetition
3. Ensure the chapter flows well with proper pacing
4. Look for any inconsistencies with characters or plot
5. Make targeted edits using edit_file to improve the chapter
6. Be precise with your search terms to avoid incorrect replacements
{summary_context}

After making edits, briefly summarize what you changed."""
                
                # Use AgentMode for agentic editing
                agent = AgentMode(
                    client=self.llm,
                    tools=[ToolDefinition(
                        name=tool.name(),
                        description=tool.description(),
                        parameters=tool.parameters_schema()
                    ) for tool in [
                        self.tools.get('read_file'),
                        self.tools.get('edit_file'),
                        self.tools.get('grep_search'),
                        self.tools.get('write_file')
                    ] if tool is not None],
                    system_message=editing_system_message,
                    max_iterations=15
                )
                
                # Tool executor that includes project_id
                def tool_executor(tool_name: str, args: Dict[str, Any]) -> Any:
                    args.setdefault('project_id', project_id)
                    tool = self.tools.get(tool_name)
                    if not tool:
                        return {'success': False, 'error': f"Unknown tool: {tool_name}"}
                    try:
                        return tool.execute(**args)
                    except Exception as e:
                        logger.error(f"Tool execution error for {tool_name}: {e}")
                        return {'success': False, 'error': str(e)}
                
                # Run the editing agent for this chapter
                result = agent.run(
                    messages=[{"role": "user", "content": edit_message}],
                    tool_executor=tool_executor
                )
                
                # Track what was edited
                editing_changes.append({
                    'chapter': chapter_num,
                    'iterations': result.get('iterations', 0),
                    'summary': result.get('content', ''),
                    'tool_calls_made': len(result.get('tool_results', [])),
                    'finished': result.get('finished', True)
                })
                
                logger.info(f"Chapter {chapter_num} editing complete: {result.get('iterations', 0)} iterations, {len(result.get('tool_results', []))} tool calls")
                
                # Save the edited chapter info to track progress
                state['editing_progress'] = editing_changes
                
                # Brief pause to avoid rate limiting
                import time
                time.sleep(1)
            
            # Generate editing summary document
            summary_content = self._generate_editing_summary(editing_changes, project, state)
            
            if 'write_file' in self.tools:
                self.tools['write_file'].execute(
                    project_id=project_id,
                    path="editing_notes.md",
                    content=summary_content
                )
            
            logger.info(f"Editing phase complete: {len(editing_changes)} chapters edited")
            
            return {
                'success': True,
                'editing_summary': summary_content,
                'chapters_edited': state['chapter_count'],
                'total_editing_iterations': sum(c['iterations'] for c in editing_changes),
                'total_tool_calls': sum(c['tool_calls_made'] for c in editing_changes),
                'changes_made': True
            }
            
        except Exception as e:
            logger.error(f"Editing phase error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}
    
    def _generate_editing_summary(self, editing_changes: List[Dict[str, Any]], project: Any, state: Dict[str, Any]) -> str:
        """
        Generate a comprehensive summary of all editing changes made.
        
        Args:
            editing_changes: List of changes made per chapter
            project: The book project
            state: Current project state
            
        Returns:
            Formatted editing summary document
        """
        from datetime import datetime
        
        lines = []
        lines.append(f"# Editing Summary for: {project.title}\n")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Project ID:** {project.id}\n")
        lines.append(f"**Genre:** {project.genre}\n")
        lines.append(f"**Total Chapters Edited:** {len(editing_changes)}\n")
        lines.append(f"**Total Words:** {state['total_words']:,}\n\n")
        lines.append("---\n\n")
        
        # Statistics
        total_iterations = sum(c.get('iterations', 0) for c in editing_changes)
        total_tool_calls = sum(c.get('tool_calls_made', 0) for c in editing_changes)
        
        lines.append("## Editing Statistics\n")
        lines.append(f"- **Total Editing Iterations:** {total_iterations}\n")
        lines.append(f"- **Total Tool Calls Made:** {total_tool_calls}\n")
        lines.append(f"- **Average Iterations per Chapter:** {total_iterations / len(editing_changes):.1f}\n\n")
        lines.append("---\n\n")
        
        # Per-chapter summary
        lines.append("## Chapter-by-Chapter Summary\n\n")
        
        for change in editing_changes:
            chapter_num = change.get('chapter', 0)
            lines.append(f"### Chapter {chapter_num}\n")
            lines.append(f"- **Iterations:** {change.get('iterations', 0)}\n")
            lines.append(f"- **Tool Calls:** {change.get('tool_calls_made', 0)}\n")
            lines.append(f"- **Notes:** {change.get('summary', 'No summary provided')}\n\n")
        
        lines.append("---\n\n")
        
        # Overall assessment
        lines.append("## Overall Assessment\n")
        lines.append("The agentic editing system has reviewed all chapters and made targeted improvements using")
        lines.append("the edit_file tool. Changes include:\n")
        lines.append("- Grammar, spelling, and punctuation corrections\n")
        lines.append("- Improved word choice and phrasing\n")
        lines.append("- Better flow and transitions\n")
        lines.append("- Character and plot consistency checks\n\n")
        lines.append("This is a first-pass edit. Additional manual review and refinement by a human editor")
        lines.append("is recommended for final publication.\n")
        
        return "".join(lines)
    
    def _parse_chapter_outline(self, outline_content: str, target_chapters: int) -> List[Dict[str, Any]]:
        """Parse chapter information from outline content."""
        chapters = []        
        # Simple parsing - in production, use more sophisticated NLP
        lines = outline_content.split('\n')
        current_chapter = None
        
        for line in lines:
            line_lower = line.lower().strip()
            if 'chapter' in line_lower and any(c.isdigit() for c in line):
                if current_chapter:
                    chapters.append(current_chapter)
                
                # Extract chapter number
                import re
                numbers = re.findall(r'\d+', line)
                chapter_num = int(numbers[0]) if numbers else len(chapters) + 1
                
                current_chapter = {
                    'number': chapter_num,
                    'title': line.strip(),
                    'summary': '',
                    'story_position': self._determine_story_position(chapter_num, target_chapters)
                }
            elif current_chapter and line.strip():
                current_chapter['summary'] += line.strip() + ' '
        
        if current_chapter:
            chapters.append(current_chapter)
        
        # Ensure we have at least target number of chapters
        while len(chapters) < target_chapters:
            chapters.append({
                'number': len(chapters) + 1,
                'title': f'Chapter {len(chapters) + 1}',
                'summary': 'Continue the story',
                'story_position': self._determine_story_position(len(chapters) + 1, target_chapters)
            })
        
        return chapters
    
    def _determine_story_position(self, chapter_num: int, total_chapters: int) -> str:
        """Determine the story position for a chapter."""
        if chapter_num == 1:
            return "opening"
        elif chapter_num >= total_chapters:
            return "resolution"
        elif chapter_num <= total_chapters * 0.25:
            return "setup"
        elif chapter_num <= total_chapters * 0.75:
            return "middle"
        else:
            return "climax"
    
    def _is_book_complete(self, project_id: str) -> bool:
        """Check if the book writing process is complete."""
        state = self.project_states[project_id]
        project = state['project']
        
        target_chapters = max(1, project.target_length // 5000)
        target_words = project.target_length
        
        return (state['chapter_count'] >= target_chapters or 
                state['total_words'] >= target_words)
    
    def get_progress(self, project_id: str) -> Dict[str, Any]:
        """Get the current progress of a writing project."""
        if project_id not in self.project_states:
            return {
                'success': False,
                'error': 'Project not found'
            }
        
        state = self.project_states[project_id]
        project = state['project']
        
        target_words = project.target_length
        current_words = state['total_words']
        progress_percentage = min(100, (current_words / target_words) * 100) if target_words > 0 else 0
        
        return {
            'success': True,
            'project_id': project_id,
            'title': project.title,
            'phase': state['current_phase'],
            'iterations': state['iterations'],
            'chapters_completed': state['chapter_count'],
            'current_words': current_words,
            'target_words': target_words,
            'progress_percentage': round(progress_percentage, 2),
            'completed': state['completed'],
            'errors': state['errors'],
            'llm_model': self.llm.config.model,
            'llm_provider': self.llm.config.provider.value
        }
    
    def generate_final_book(self, project_id: str) -> Optional[str]:
        """Generate the final book content by reading all chapters."""
        try:
            if not self._ensure_project_state(project_id):
                return None
            
            state = self.project_states[project_id]
            project = state['project']
            
            content_parts = []
            
            # Add title page
            content_parts.append(f"# {project.title}")
            content_parts.append(f"Genre: {project.genre}")
            content_parts.append(f"Target Length: {project.target_length:,} words")
            content_parts.append(f"Writing Style: {project.writing_style}")
            content_parts.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content_parts.append(f"AI Model: {self.llm.config.model}")
            content_parts.append("\n" + "="*50 + "\n")
            
            # Read chapters
            for i in range(1, state['chapter_count'] + 1):
                try:
                    if 'read_file' in self.tools:
                        chapter_result = self.tools['read_file'].execute(
                            project_id=project_id,
                            path=f"chapters/chapter_{i}.md"
                        )
                        
                        if chapter_result.get('success'):
                            content_parts.append(chapter_result['content'])
                            content_parts.append("\n" + "-"*30 + "\n")
                except Exception as e:
                    logger.warning(f"Could not read chapter {i}: {e}")
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error generating final book: {e}")
            return None
    
    def execute_step(self, project, step_type: str) -> Dict[str, Any]:
        """Execute a specific step for debugging or manual control."""
        try:
            project_id = project.id
            
            if project_id not in self.project_states:
                # Initialize state if not exists
                self.project_states[project_id] = {
                    'project': project,
                    'current_phase': step_type,
                    'chapter_count': 0,
                    'total_words': 0,
                    'iterations': 0,
                    'completed': False,
                    'errors': [],
                    'conversation_history': []
                }
            
            state = self.project_states[project_id]
            
            if step_type == "planning":
                return self._execute_planning_phase(project_id)
            
            elif step_type == "research":
                return self._execute_research_phase(project_id)
            
            elif step_type == "write_chapter":
                return self._write_chapter_with_llm(project_id)
            
            elif step_type == "edit":
                return self._execute_editing_phase(project_id)
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown step type: {step_type}'
                }
                
        except Exception as e:
            logger.error(f"Error executing step {step_type}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def chat_with_agent(
        self, 
        project_id: str, 
        user_message: str,
        use_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Have a conversation with the agent about the book project using an agentic loop.
        
        Uses the AgentMode class which implements the proper OpenAI tool calling loop:
        1. Send messages to LLM
        2. If LLM returns tool calls → execute each tool
        3. Add tool results as role="tool" messages
        4. Loop back to step 1 with ALL messages (including tool results)
        5. Return final response when no more tool calls
        """
        try:
            if not self._ensure_project_state(project_id):
                return {
                    'success': False,
                    'error': 'Project not found. Please start the writing process first.'
                }
            
            state = self.project_states[project_id]
            project = state['project']
            
            # Build system message
            system_message = f"""You are a professional AI Writing Agent working on the book "{project.title}".
Your role is similar to a "coding agent" (like Cursor or Windsurf) but specialized for creative writing and book production.

Current Project Status:
- Title: {project.title}
- Genre: {project.genre}
- Current Phase: {state['current_phase']}
- Chapters Completed: {state['chapter_count']}
- Total Words: {state['total_words']:,}

Project Structure:
- `outline.md`: The book's structure and chapter summaries.
- `research_notes.md`: Background information and world-building.
- `editing_notes.md`: Initial editing suggestions.
- `chapters/`: Directory containing all chapter files (e.g., `chapters/chapter_1.md`).

Your Capabilities:
1.  **File Operations**: You can read, write, and edit all project files.
2.  **Structural Editing**: You can change the book outline, rewrite chapters, or adjust plot points.
3.  **Creative Collaboration**: You can brainstorm ideas, develop characters, and provide stylistic advice.
4.  **Consistency Management**: You can ensure names, dates, and world-building facts remain consistent.

Tool Usage Guidelines:
- **read_file**: Use this to examine existing chapters or notes. It will provide line numbers.
- **edit_file**: Use this for fine-grained changes. Provide the exact text to search for and the replacement.
- **write_file**: Use this for full chapter rewrites or creating new supporting documents.
- **list_directory**: Use this to see the project structure (typically 'chapters/', 'outline.md', etc.)

Always be proactive. If a user asks for a change, read the relevant file first, then apply the edits. 
After performing tool actions, explain exactly what you changed and why.

Always include "project_id": "{project_id}" in every tool call.
Paths are relative to the project root (e.g., "chapters/chapter_1.md")."""

            # Add user message to history
            state.setdefault('conversation_history', [])
            state['conversation_history'].append({"role": "user", "content": user_message})
            
            # Build conversation messages (exclude system message - handled by AgentMode)
            messages = list(state['conversation_history'][-15:])
            
            # Custom tool executor that includes project_id
            def tool_executor(tool_name: str, args: Dict[str, Any]) -> Any:
                args.setdefault('project_id', project_id)
                tool = self.tools.get(tool_name)
                if not tool:
                    return {'success': False, 'error': f"Unknown tool: {tool_name}"}
                try:
                    return tool.execute(**args)
                except Exception as e:
                    return {'success': False, 'error': str(e)}
            
            # Use AgentMode for proper tool loop
            if use_tools and self.tool_definitions:
                agent = AgentMode(
                    client=self.llm,
                    tools=self.tool_definitions,
                    system_message=system_message,
                    max_iterations=20
                )
                result = agent.run(
                    messages=messages,
                    tool_executor=tool_executor
                )
            else:
                # No tools, just chat
                response = self.llm.chat(
                    messages=[{"role": "system", "content": system_message}] + messages
                )
                result = {
                    'content': response.content,
                    'tool_results': [],
                    'iterations': 1,
                    'finished': True,
                    'usage': response.usage
                }
            
            # Update conversation history with agent's response
            assistant_msg = {"role": "assistant", "content": result.get('content', '')}
            if result.get('tool_results'):
                # Convert tool results back to assistant message format
                tool_calls = []
                for tr in result['tool_results']:
                    tool_calls.append({
                        'id': tr.get('tool_call_id'),
                        'type': 'function',
                        'function': {
                            'name': tr.get('tool_name'),
                            'arguments': json.dumps(tr.get('arguments', {}))
                        }
                    })
                assistant_msg["tool_calls"] = tool_calls
            state['conversation_history'].append(assistant_msg)
            
            # Add tool results to history
            for tr in result.get('tool_results', []):
                state['conversation_history'].append({
                    "role": "tool",
                    "tool_call_id": tr.get('tool_call_id'),
                    "name": tr.get('tool_name'),
                    "content": json.dumps(tr.get('result', {}))
                })
            
            self._save_project_state(project_id)
            
            # Generate proactive suggestions based on project state
            suggestions = self._generate_chat_suggestions(project_id, state)
            
            return {
                'success': True,
                'response': result.get('content', ''),
                'tool_calls': result.get('tool_results', []),
                'iterations': result.get('iterations', 1),
                'finished': result.get('finished', True),
                'suggestions': suggestions
            }
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    def _generate_chat_suggestions(self, project_id: str, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate proactive suggestions based on current project state.
        
        Returns a list of suggested actions the user might want to take,
        such as checking character consistency, evaluating chapters, or
        updating the story outline.
        """
        suggestions = []
        project = state.get('project')
        
        if not project:
            return suggestions
        
        # Suggestion 1: If book has chapters but no editing phase yet
        if state['current_phase'] in ['writing', 'research', 'planning'] and state['chapter_count'] >= 3:
            suggestions.append({
                'type': 'editing_suggestion',
                'title': 'Review and Edit Chapters',
                'description': f'You have {state["chapter_count"]} chapters written. Consider running the editing phase to review for grammar, consistency, and quality.'
            })
        
        # Suggestion 2: If we have a running summary with characters
        running_summary = state.get('running_summary', {})
        if running_summary.get('characters_introduced') and len(running_summary['characters_introduced']) > 2:
            suggestions.append({
                'type': 'consistency_check',
                'title': 'Check Character Consistency',
                'description': f'You have introduced {len(running_summary["characters_introduced"])} characters so far. Consider checking for consistent character descriptions across chapters.'
            })
        
        # Suggestion 3: If book is in editing phase but has potential issues
        if state['current_phase'] == 'editing':
            consistency_notes = state.get('consistency_notes', [])
            if consistency_notes:
                suggestions.append({
                    'type': 'consistency_review',
                    'title': 'Review Cross-Chapter Consistency',
                    'description': f'Found {len(consistency_notes)} consistency notes during editing. Review character and location mentions across chapters.'
                })
        
        # Suggestion 4: If book is near completion
        if state['current_phase'] == 'refining' or state.get('completed', False):
            suggestions.append({
                'type': 'export_suggestion',
                'title': 'Export Your Book',
                'description': 'Your book is ready! Consider exporting to PDF, EPUB, DOCX, or plain text formats.'
            })
        
        # Suggestion 5: If writing phase and chapter count is low
        if state['current_phase'] == 'writing' and state['chapter_count'] < 5:
            suggestions.append({
                'type': 'outline_review',
                'title': 'Review Chapter Outline',
                'description': 'Consider reviewing your chapter outline to ensure pacing and plot structure align with your vision.'
            })
        
        return suggestions


    def chat_with_agent_stream(
        self, 
        project_id: str, 
        user_message: str,
        use_tools: bool = True
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream a conversation with the AI agent about the book project.
        
        Uses the AgentMode.run_stream() method which implements the proper OpenAI 
        tool calling loop with streaming support.
        
        Yields:
            Dictionary with streaming updates:
            - {'type': 'content', 'data': 'streaming text'}
            - {'type': 'tool_call', 'data': {'function': {...}, 'id': '...'}}
            - {'type': 'tool_result', 'data': {'result': {...}, 'tool_call_id': '...'}}
            - {'type': 'turn_complete', 'data': {'iteration': 1}}
            - {'type': 'complete', 'data': {'content': 'final content', 'finished': True}}
        """
        try:
            if not self._ensure_project_state(project_id):
                yield {'type': 'error', 'data': 'Project not found.'}
                return
            
            state = self.project_states[project_id]
            project = state['project']
            
            # Build system message
            system_message = f"""You are a professional AI Writing Agent working on the book "{project.title}".
Your role is similar to a "coding agent" (like Cursor or Windsurf) but specialized for creative writing and book production.

Current Project Status:
- Title: {project.title}
- Genre: {project.genre}
- Current Phase: {state['current_phase']}
- Chapters Completed: {state['chapter_count']}
- Total Words: {state['total_words']:,}

Project Structure:
- `outline.md`: The book's structure and chapter summaries.
- `research_notes.md`: Background information and world-building.
- `editing_notes.md`: Initial editing suggestions.
- `chapters/`: Directory containing all chapter files (e.g., `chapters/chapter_1.md`).

Your Capabilities:
1.  **File Operations**: You can read, write, and edit all project files.
2.  **Structural Editing**: You can change the book outline, rewrite chapters, or adjust plot points.
3.  **Creative Collaboration**: You can brainstorm ideas, develop characters, and provide stylistic advice.
4.  **Consistency Management**: You can ensure names, dates, and world-building facts remain consistent.

Tool Usage Guidelines:
- **read_file**: Use this to examine existing chapters or notes. It will provide line numbers.
- **edit_file**: Use this for fine-grained changes. Provide the exact text to search for and the replacement.
- **write_file**: Use this for full chapter rewrites or creating new supporting documents.
- **list_directory**: Use this to see the project structure (typically 'chapters/', 'outline.md', etc.)

Always be proactive. If a user asks for a change, read the relevant file first, then apply the edits. 
After performing tool actions, explain exactly what you changed and why.

Always include "project_id": "{project_id}" in every tool call.
Paths are relative to the project root (e.g., "chapters/chapter_1.md")."""

            # Add user message to history
            state.setdefault('conversation_history', [])
            state['conversation_history'].append({"role": "user", "content": user_message})
            
            # Get initial messages (without system - handled by AgentMode)
            messages = list(state['conversation_history'][-15:])
            
            # Custom tool executor
            def tool_executor(tool_name: str, args: Dict[str, Any]) -> Any:
                args.setdefault('project_id', project_id)
                tool = self.tools.get(tool_name)
                if not tool:
                    return {'success': False, 'error': f"Unknown tool: {tool_name}"}
                try:
                    return tool.execute(**args)
                except Exception as e:
                    return {'success': False, 'error': str(e)}
            
            # Use AgentMode with streaming
            if use_tools and self.tool_definitions:
                agent = AgentMode(
                    client=self.llm,
                    tools=self.tool_definitions,
                    system_message=system_message,
                    max_iterations=20
                )
                
                # Forward all streaming updates
                for update in agent.run_stream(messages, tool_executor=tool_executor):
                    if update['type'] == 'turn_complete':
                        # Persist state after each turn. We intentionally do NOT
                        # append a placeholder here — the assistant message is
                        # recorded below when the run completes, so adding a
                        # "Thinking..." stub would duplicate/pollute the history.
                        self._save_project_state(project_id)
                    elif update['type'] == 'complete':
                        # Add the final assistant response to history once.
                        final_content = update['data'].get('content', '')
                        state['conversation_history'].append({
                            "role": "assistant",
                            "content": final_content
                        })
                        self._save_project_state(project_id)
                        
                        # Generate and yield suggestions
                        suggestions = self._generate_chat_suggestions(project_id, state)
                        if suggestions:
                            yield {
                                'type': 'suggestions',
                                'data': suggestions
                            }

                    yield update
            else:
                # No tools - just stream regular chat
                all_messages = [{"role": "system", "content": system_message}] + messages
                for chunk in self.llm.chat_stream(all_messages):
                    yield {'type': 'content', 'data': chunk}
                yield {'type': 'complete', 'data': {'content': '', 'finished': True}}
                
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            yield {
                'type': 'error',
                'data': f'Chat error: {str(e)}'
            }

    # =============================================================================
    # ANALYTICS DASHBOARD COMPONENTS
    # =============================================================================

    def generate_pacing_analysis(self, project_id: str) -> Dict[str, Any]:
        """
        Generate pacing analysis showing scene lengths and tension levels.
        
        Returns:
            Dict with pacing data and insights
        """
        try:
            state = self.project_states.get(project_id, {})
            project = state.get('project') if state else None
            
            if not project:
                return {'success': False, 'error': 'Project not found'}
            
            # Analyze chapter lengths and pacing
            chapter_lengths = []
            for i in range(1, state.get('chapter_count', 0) + 1):
                try:
                    read_tool = self.tools.get('read_file')
                    if read_tool:
                        result = read_tool.execute(
                            project_id=project_id,
                            path=f"chapters/chapter_{i}.md"
                        )
                        content = result.get('content', '') if isinstance(result, dict) else str(result)
                        chapter_lengths.append({'chapter': i, 'words': len(content.split())})
                except Exception:
                    pass
            
            # Calculate pacing insights
            avg_length = sum(c['words'] for c in chapter_lengths) / len(chapter_lengths) if chapter_lengths else 0
            min_length = min((c['words'] for c in chapter_lengths), default=0)
            max_length = max((c['words'] for c in chapter_lengths), default=0)
            
            return {
                'success': True,
                'chapter_lengths': chapter_lengths,
                'average_words': round(avg_length, 2),
                'min_words': min_length,
                'max_words': max_length,
                'pacing_insights': f"Average chapter length: {round(avg_length)} words. Range: {min_length}-{max_length} words."
            }
        except Exception as e:
            logger.error(f"Error generating pacing analysis: {e}")
            return {'success': False, 'error': str(e)}

    def generate_character_frequency(self, project_id: str) -> Dict[str, Any]:
        """
        Track which characters appear most/least across chapters.
        
        Returns:
            Dict with character frequency data
        """
        try:
            state = self.project_states.get(project_id, {})
            running_summary = state.get('running_summary', {})
            characters = running_summary.get('characters_introduced', [])
            
            # In a full implementation, this would use grep_search to count mentions
            # For now, return the characters introduced with placeholder frequency data
            character_freq = {}
            for char in characters[:10]:  # Limit to first 10 characters
                character_freq[char] = {
                    'mentions': 0,  # Would be counted via grep_search
                    'first_appearance': None,
                    'last_appearance': None
                }
            
            return {
                'success': True,
                'characters_analyzed': characters,
                'frequency_data': character_freq,
                'insights': f"Analyzed {len(characters)} introduced characters. Use consistency checks for detailed mention tracking."
            }
        except Exception as e:
            logger.error(f"Error generating character frequency: {e}")
            return {'success': False, 'error': str(e)}

    def generate_readability_score(self, project_id: str) -> Dict[str, Any]:
        """
        Calculate readability metrics (Flesch-Kincaid or similar) for target audience alignment.
        
        Returns:
            Dict with readability scores and insights
        """
        try:
            state = self.project_states.get(project_id, {})
            project = state.get('project') if state else None
            
            if not project:
                return {'success': False, 'error': 'Project not found'}
            
            # Read a sample chapter to calculate readability
            try:
                read_tool = self.tools.get('read_file')
                if read_tool:
                    result = read_tool.execute(
                        project_id=project_id,
                        path=f"chapters/chapter_1.md"
                    )
                    content = result.get('content', '') if isinstance(result, dict) else str(result)
                    
                    # Simple readability calculation (Flesch-Kincaid approximation)
                    sentences = len([s for s in content.split('.') if s.strip()])
                    words = len(content.split())
                    syllables = 0
                    for word in content.split():
                        word = word.lower()
                        if len(word) <= 3:
                            syllables += 1
                        else:
                            vowels = sum(1 for c in word if c.lower() in 'aeiou')
                            syllables += max(1, vowels)
                    
                    if sentences > 0 and words > 0:
                        # Flesch-Kincaid Grade Level formula
                        fk_grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
                        fk_score = max(0, round(fk_grade, 2))
                    else:
                        fk_score = 0
                    
                    return {
                        'success': True,
                        'sample_chapters_analyzed': 1,
                        'flesch_kincaid_grade': fk_score,
                        'interpretation': f"Reading level approximately {fk_score}th grade. " + 
                                         ('Suitable for general adult readers.' if fk_score < 12 else 'May be complex for general audience.'),
                        'words_sampled': words
                    }
            except Exception as e:
                logger.warning(f"Could not calculate readability score: {e}")
                return {
                    'success': True,
                    'flesch_kincaid_grade': None,
                    'interpretation': 'Readability analysis pending chapter generation.',
                    'words_sampled': 0
                }
        except Exception as e:
            logger.error(f"Error generating readability score: {e}")
            return {'success': False, 'error': str(e)}

    def generate_pdf_book(self, project_id: str) -> Optional[bytes]:
        """
        Generate a PDF of the book with proper formatting.

        Args:
            project_id: The project identifier

        Returns:
            PDF content as bytes, or None if generation fails
        """
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
            from io import BytesIO

            if not self._ensure_project_state(project_id):
                return None

            state = self.project_states[project_id]
            project = state['project']

            # Create PDF in memory
            buffer = BytesIO()

            # Create the PDF document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )

            # Get styles
            styles = getSampleStyleSheet()

            # Create custom styles
            title_style = ParagraphStyle(
                'BookTitle',
                parent=styles['Heading1'],
                fontSize=24,
                alignment=TA_CENTER,
                spaceAfter=30
            )

            chapter_style = ParagraphStyle(
                'ChapterTitle',
                parent=styles['Heading2'],
                fontSize=18,
                spaceBefore=20,
                spaceAfter=12
            )

            body_style = ParagraphStyle(
                'BookBody',
                parent=styles['Normal'],
                fontSize=11,
                alignment=TA_JUSTIFY,
                spaceAfter=12,
                leading=14
            )

            # Build the story (content)
            story = []

            # Title page
            story.append(Spacer(1, 2*inch))
            story.append(Paragraph(project.title, title_style))
            story.append(Spacer(1, 0.5*inch))
            story.append(Paragraph(f"<i>{project.genre}</i>", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph(f"Target Length: {project.target_length:,} words", styles['Normal']))
            story.append(Paragraph(f"Writing Style: {project.writing_style}", styles['Normal']))
            story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
            story.append(PageBreak())

            # Table of Contents placeholder
            story.append(Paragraph("Table of Contents", styles['Heading1']))
            story.append(Spacer(1, 0.3*inch))

            # Read all chapters and add to TOC
            chapters = []
            for i in range(1, state['chapter_count'] + 1):
                chapter_result = self.tools['read_file'].execute(
                    project_id=project_id,
                    path=f"chapters/chapter_{i}.md"
                )
                if chapter_result.get('success'):
                    chapters.append({
                        'number': i,
                        'content': chapter_result['content']
                    })
                    story.append(Paragraph(f"Chapter {i}", styles['Normal']))

            story.append(PageBreak())

            # Add chapters
            for chapter in chapters:
                story.append(Paragraph(f"Chapter {chapter['number']}", chapter_style))
                story.append(Spacer(1, 0.2*inch))

                # Parse content - remove line numbers if present and format
                content = chapter['content']
                # Clean up the content (remove line number prefixes)
                lines = []
                for line in content.split('\n'):
                    # Remove line number prefixes like "   1 | "
                    if '|' in line and line.strip().split('|')[0].strip().isdigit():
                        line = line.split('|', 1)[1].strip() if '|' in line else line
                    lines.append(line)
                clean_content = '\n'.join(lines)

                # Split into paragraphs and add
                paragraphs = clean_content.split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        # Escape special characters for reportlab
                        para = para.replace('&', '&amp;')
                        para = para.replace('<', '&lt;')
                        para = para.replace('>', '&gt;')
                        para = para.replace('\n', '<br/>')
                        try:
                            story.append(Paragraph(para, body_style))
                        except Exception as e:
                            # If paragraph fails, add as preformatted
                            story.append(Paragraph(f"<pre>{para}</pre>", body_style))

                story.append(PageBreak())

            # Build the PDF
            doc.build(story)

            # Get the PDF bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()

            logger.info(f"Generated PDF for project {project_id}: {len(pdf_bytes)} bytes")
            return pdf_bytes

        except ImportError as e:
            logger.error(f"ReportLab not installed: {e}")
            logger.error("Install with: pip install reportlab")
            return None
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

