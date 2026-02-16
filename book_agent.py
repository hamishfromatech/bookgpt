"""
Book Writing Agent - Implements agentic loop with tool calling for autonomous book writing.

This agent uses OpenAI (or OpenAI-compatible APIs) for real AI-powered book generation,
following the patterns from OpenAI's function calling and coding agent templates.
"""

import json
import uuid
import os
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime
import logging

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


class BookWritingAgent:
    """
    Main agent for autonomous book writing using agentic loops and tool calling.
    
    This agent supports:
    1. OpenAI API (default)
    2. Custom base URLs for OpenAI-compatible APIs
    3. Local LLM servers (Ollama, LM Studio, vLLM, etc.)
    
    Configuration via environment variables:
    - OPENAI_API_KEY: Your API key
    - OPENAI_BASE_URL: Custom base URL (optional)
    - LLM_MODEL: Model to use (default: gpt-4o)
    """
    
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
        self.progress_callback = None
        self.db = db or BookDatabase()
        
        # Agent configuration
        self.max_iterations = 20
        self.current_iteration = 0
        
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
    
    def _ensure_project_state(self, project_id: str) -> bool:
        """Ensure the project state is loaded into memory."""
        if project_id in self.project_states:
            return True
            
        logger.info(f"Loading project state from database for: {project_id}")
        project = self.db.get_project(project_id)
        if not project:
            logger.error(f"Project {project_id} not found in database")
            return False
            
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
            'research_materials': project.research_materials or {}
        }
        return True

    def _save_project_state(self, project_id: str):
        """Save the project state to the database."""
        if project_id not in self.project_states:
            return
            
        state = self.project_states[project_id]
        project = state['project']
        
        # Update project object with current state
        project.status = state['current_phase']
        project.chapters_completed = state['chapter_count']
        project.total_words = state['total_words']
        project.outline = state.get('outline')
        project.research_materials = state.get('research_materials')
        
        # Save conversation history in metadata
        project.metadata['conversation_history'] = state.get('conversation_history', [])
        
        # Persist to database
        self.db.save_project(project)
        logger.info(f"Project state saved to database for: {project_id}")

    def set_progress_callback(self, callback):
        """Set a callback function to receive progress updates."""
        self.progress_callback = callback
    
    def _report_progress(self, phase: str, progress: float, message: str, activity: str = None):
        """Report progress to the callback if set."""
        if self.progress_callback:
            self.progress_callback(phase, progress, message, activity)
    
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
    
    def _run_agentic_loop(self, project_id: str) -> Dict[str, Any]:
        """Main agentic loop that handles the book writing process."""
        
        state = self.project_states[project_id]
        project = state['project']
        
        try:
            # Phase 1: Planning and Outline Generation
            if state['current_phase'] == 'planning':
                logger.info("Phase 1: Planning and Outline Generation")
                self._report_progress('planning', 10.0, 'Creating book outline and structure...', 'Starting planning phase')
                
                planning_result = self._execute_planning_phase(project_id)
                
                if planning_result['success']:
                    state['outline'] = planning_result.get('outline', {})
                    state['current_phase'] = 'research'
                    self._report_progress('planning', 100.0, 'Planning completed successfully', 'Outline created successfully')
                    logger.info("Outline created successfully, moving to research phase")
                    self._save_project_state(project_id)
                else:
                    state['errors'].append(f"Planning failed: {planning_result.get('error')}")
                    self._save_project_state(project_id)
                    return planning_result
            
            # Phase 2: Research and Background
            if state['current_phase'] == 'research':
                logger.info("Phase 2: Research and Background")
                self._report_progress('research', 30.0, 'Gathering background information...', 'Starting research phase')
                
                research_result = self._execute_research_phase(project_id, state['outline'])
                
                if research_result['success']:
                    state['research_materials'] = research_result.get('materials', {})
                    state['current_phase'] = 'writing'
                    self._report_progress('research', 100.0, 'Research completed successfully', 'Research phase completed')
                    logger.info("Research completed, moving to writing phase")
                    self._save_project_state(project_id)
                else:
                    state['errors'].append(f"Research failed: {research_result.get('error')}")
                    self._save_project_state(project_id)
                    return research_result
            
            # Phase 3: Chapter Writing Loop
            while state['current_phase'] == 'writing' and state['iterations'] < self.max_iterations:
                logger.info(f"Phase 3: Writing Chapter {state['chapter_count'] + 1}")
                
                chapter_result = self._write_chapter_with_llm(project_id)
                
                if chapter_result['success']:
                    state['chapter_count'] += 1
                    state['total_words'] += chapter_result.get('words_written', 0)
                    state['iterations'] += 1
                    
                    if self._is_book_complete(project_id):
                        state['current_phase'] = 'editing'
                        logger.info("All chapters written, moving to editing phase")
                    
                    self._save_project_state(project_id)
                    
                    if state['current_phase'] == 'editing':
                        break
                else:
                    state['errors'].append(f"Chapter writing failed: {chapter_result.get('error')}")
                    self._save_project_state(project_id)
                    return chapter_result
            
            # Phase 4: Editing and Refinement
            if state['current_phase'] == 'editing':
                logger.info("Phase 4: Editing and Refinement")
                
                edit_result = self._execute_editing_phase(project_id)
                
                if edit_result['success']:
                    state['current_phase'] = 'refining'
                    state['completed'] = True
                    logger.info("Editing completed successfully, entering Agent Mode")
                    self._save_project_state(project_id)
                else:
                    state['errors'].append(f"Editing failed: {edit_result.get('error')}")
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
    
    def _execute_planning_phase(self, project_id: str) -> Dict[str, Any]:
        """Execute the planning phase using LLM."""
        state = self.project_states[project_id]
        project = state['project']
        
        try:
            logger.info(f"Starting planning phase for project: {project.title}")
            
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPTS["planning"]},
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
                {"role": "system", "content": self.SYSTEM_PROMPTS["research"]},
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
                
                self._report_progress('writing', 30.0 + (i / len(chapters)) * 60.0, 
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
    
    def _write_chapter_with_llm(self, project_id: str) -> Dict[str, Any]:
        """Write a chapter using the LLM."""
        state = self.project_states[project_id]
        project = state['project']
        chapter_number = state['chapter_count'] + 1
        outline = state.get('outline', {})
        research = state.get('research_materials', {})
        
        try:
            # Get chapter-specific guidance from outline
            chapters = outline.get('chapters', [])
            chapter_guidance = ""
            total_expected_chapters = len(chapters) if chapters else max(1, project.target_length // 5000)
            
            # Report progress
            progress = 30.0 + (min(chapter_number - 1, total_expected_chapters) / total_expected_chapters) * 60.0
            self._report_progress('writing', progress, f'Writing chapter {chapter_number} of {total_expected_chapters}...', f'Writing: {project.title} - Chapter {chapter_number}')

            if chapter_number <= len(chapters):
                chapter_info = chapters[chapter_number - 1]
                chapter_guidance = f"\nChapter {chapter_number} should cover: {chapter_info.get('summary', 'Continue the story')}"
            
            # Build context from previous chapters
            previous_context = ""
            if chapter_number > 1:
                previous_context = "\n\nPrevious chapter summaries are available in the outline."
            
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPTS["writing"]},
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
            
            response = self.llm.chat(messages, max_tokens=4096)
            
            if response.content:
                chapter_content = response.content
                word_count = len(chapter_content.split())
                
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
                return {
                    'success': False,
                    'error': f'No content generated for chapter {chapter_number}'
                }
                
        except Exception as e:
            logger.error(f"Chapter writing error: {e}")
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

            # Iterate through each chapter and use AgentMode to edit it
            for chapter_num in range(1, state['chapter_count'] + 1):
                logger.info(f"Editing chapter {chapter_num} of {state['chapter_count']}")
                
                # Update progress
                progress = 30 + ((chapter_num - 1) / state['chapter_count']) * 60
                self._report_progress('editing', progress, f'Editing chapter {chapter_num}...', f'Processing chapter {chapter_num}/{state["chapter_count"]}')
                
                # Initial message to start editing this chapter
                edit_message = f"""Review and edit chapter {chapter_num}.

Read the full chapter file at chapters/chapter_{chapter_num}.md, then:

1. Identify grammar, punctuation, and spelling errors
2. Check for awkward phrasing or word repetition
3. Ensure the chapter flows well with proper pacing
4. Look for any inconsistencies with characters or plot
5. Make targeted edits using edit_file to improve the chapter
6. Be precise with your search terms to avoid incorrect replacements

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
            
            return {
                'success': True,
                'response': result.get('content', ''),
                'tool_calls': result.get('tool_results', []),
                'iterations': result.get('iterations', 1),
                'finished': result.get('finished', True)
            }
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}


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
                        # Save state after each turn
                        self._save_project_state(project_id)
                        
                        # Update conversation history with messages from this turn
                        # Note: AgentMode doesn't expose internal history, so we add basic structure
                        state['conversation_history'].append({
                            "role": "assistant",
                            "content": "Thinking..."
                        })
                    elif update['type'] == 'complete':
                        self._save_project_state(project_id)
                        
                        # Add final response to history
                        state['conversation_history'].append({
                            "role": "assistant",
                            "content": update['data'].get('content', '')
                        })
                    
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

