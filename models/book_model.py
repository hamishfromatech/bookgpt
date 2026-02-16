"""
Data models for BookGPT application.

These models represent the book project structure and state management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

@dataclass
class BookProject:
    """Model representing a book writing project."""
    
    id: str
    user_id: str
    title: str
    genre: str
    target_length: int
    writing_style: str
    status: str = "created"
    outline: Optional[Dict[str, Any]] = None
    research_materials: Optional[Dict[str, Any]] = None
    chapters_completed: int = 0
    total_words: int = 0
    current_chapter: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'genre': self.genre,
            'target_length': self.target_length,
            'writing_style': self.writing_style,
            'status': self.status,
            'outline': self.outline,
            'research_materials': self.research_materials,
            'chapters_completed': self.chapters_completed,
            'total_words': self.total_words,
            'current_chapter': self.current_chapter,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BookProject':
        """Create project from dictionary."""
        # Parse datetime fields
        created_at = datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now()
        updated_at = datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now()
        completed_at = datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None
        
        return cls(
            id=data['id'],
            user_id=data['user_id'],
            title=data['title'],
            genre=data['genre'],
            target_length=data['target_length'],
            writing_style=data['writing_style'],
            status=data.get('status', 'created'),
            outline=data.get('outline'),
            research_materials=data.get('research_materials'),
            chapters_completed=data.get('chapters_completed', 0),
            total_words=data.get('total_words', 0),
            current_chapter=data.get('current_chapter', 0),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
            metadata=data.get('metadata', {})
        )
    
    def update_progress(self, chapters_completed: int = None, total_words: int = None, 
                       current_chapter: int = None, status: str = None):
        """Update project progress and timestamp."""
        if chapters_completed is not None:
            self.chapters_completed = chapters_completed
        if total_words is not None:
            self.total_words = total_words
        if current_chapter is not None:
            self.current_chapter = current_chapter
        if status is not None:
            self.status = status
            if status == 'completed':
                self.completed_at = datetime.now()
        
        self.updated_at = datetime.now()
    
    def get_progress_percentage(self) -> float:
        """Calculate progress percentage based on word count."""
        if self.target_length <= 0:
            return 0.0
        
        percentage = (self.total_words / self.target_length) * 100
        return min(100.0, percentage)

@dataclass
class Chapter:
    """Model representing a single chapter."""
    
    id: str
    project_id: str
    chapter_number: int
    title: str
    content: str = ""
    word_count: int = 0
    status: str = "draft"  # draft, editing, completed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'chapter_number': self.chapter_number,
            'title': self.title,
            'content': self.content,
            'word_count': self.word_count,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chapter':
        """Create chapter from dictionary."""
        created_at = datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now()
        updated_at = datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now()
        
        return cls(
            id=data['id'],
            project_id=data['project_id'],
            chapter_number=data['chapter_number'],
            title=data['title'],
            content=data.get('content', ''),
            word_count=data.get('word_count', 0),
            status=data.get('status', 'draft'),
            created_at=created_at,
            updated_at=updated_at,
            notes=data.get('notes', '')
        )
    
    def update_content(self, content: str):
        """Update chapter content and recalculate word count."""
        self.content = content
        self.word_count = len(content.split())
        self.updated_at = datetime.now()

@dataclass
class AgentExecution:
    """Model representing an agent execution step."""
    
    id: str
    project_id: str
    step_type: str
    input_prompt: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to dictionary."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'step_type': self.step_type,
            'input_prompt': self.input_prompt,
            'tool_calls': self.tool_calls,
            'results': self.results,
            'status': self.status,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'execution_time': self.execution_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentExecution':
        """Create execution from dictionary."""
        started_at = datetime.fromisoformat(data['started_at']) if data.get('started_at') else datetime.now()
        completed_at = datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None
        
        return cls(
            id=data['id'],
            project_id=data['project_id'],
            step_type=data['step_type'],
            input_prompt=data['input_prompt'],
            tool_calls=data.get('tool_calls', []),
            results=data.get('results', []),
            status=data.get('status', 'pending'),
            started_at=started_at,
            completed_at=completed_at,
            error_message=data.get('error_message'),
            execution_time=data.get('execution_time')
        )
    
    def mark_completed(self):
        """Mark execution as completed."""
        self.status = "completed"
        self.completed_at = datetime.now()
        if self.started_at:
            self.execution_time = (self.completed_at - self.started_at).total_seconds()
    
    def mark_failed(self, error_message: str):
        """Mark execution as failed."""
        self.status = "failed"
        self.error_message = error_message
        self.completed_at = datetime.now()
        if self.started_at:
            self.execution_time = (self.completed_at - self.started_at).total_seconds()

@dataclass
class ProjectStats:
    """Model representing project statistics."""
    
    project_id: str
    total_sessions: int = 0
    total_agent_steps: int = 0
    total_files_created: int = 0
    average_chapter_length: float = 0.0
    writing_velocity: float = 0.0  # words per hour
    most_productive_hour: int = 0
    last_activity: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            'project_id': self.project_id,
            'total_sessions': self.total_sessions,
            'total_agent_steps': self.total_agent_steps,
            'total_files_created': self.total_files_created,
            'average_chapter_length': self.average_chapter_length,
            'writing_velocity': self.writing_velocity,
            'most_productive_hour': self.most_productive_hour,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectStats':
        """Create stats from dictionary."""
        last_activity = datetime.fromisoformat(data['last_activity']) if data.get('last_activity') else None
        
        return cls(
            project_id=data['project_id'],
            total_sessions=data.get('total_sessions', 0),
            total_agent_steps=data.get('total_agent_steps', 0),
            total_files_created=data.get('total_files_created', 0),
            average_chapter_length=data.get('average_chapter_length', 0.0),
            writing_velocity=data.get('writing_velocity', 0.0),
            most_productive_hour=data.get('most_productive_hour', 0),
            last_activity=last_activity
        )