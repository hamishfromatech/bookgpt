"""
Version history models for tracking chapter edits and changes.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import uuid


@dataclass
class ChapterVersion:
    """Model representing a version of a chapter."""

    id: str
    chapter_id: str
    project_id: str
    version_number: int
    content: str
    word_count: int
    created_at: datetime
    created_by: str  # 'agent' or user_id
    change_summary: str = ""
    parent_version_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'chapter_id': self.chapter_id,
            'project_id': self.project_id,
            'version_number': self.version_number,
            'content': self.content,
            'word_count': self.word_count,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'change_summary': self.change_summary,
            'parent_version_id': self.parent_version_id,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChapterVersion':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            chapter_id=data['chapter_id'],
            project_id=data['project_id'],
            version_number=data['version_number'],
            content=data['content'],
            word_count=data['word_count'],
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at', datetime.now()),
            created_by=data.get('created_by', 'agent'),
            change_summary=data.get('change_summary', ''),
            parent_version_id=data.get('parent_version_id'),
            metadata=data.get('metadata', {})
        )


@dataclass
class Character:
    """Model representing a character in the book."""

    id: str
    project_id: str
    name: str
    description: str = ""
    role: str = ""  # protagonist, antagonist, supporting, etc.
    first_appearance_chapter: Optional[int] = None
    last_appearance_chapter: Optional[int] = None
    traits: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)  # character_id -> relationship_type
    backstory: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'description': self.description,
            'role': self.role,
            'first_appearance_chapter': self.first_appearance_chapter,
            'last_appearance_chapter': self.last_appearance_chapter,
            'traits': self.traits,
            'relationships': self.relationships,
            'backstory': self.backstory,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Character':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            project_id=data['project_id'],
            name=data['name'],
            description=data.get('description', ''),
            role=data.get('role', ''),
            first_appearance_chapter=data.get('first_appearance_chapter'),
            last_appearance_chapter=data.get('last_appearance_chapter'),
            traits=data.get('traits', []),
            relationships=data.get('relationships', {}),
            backstory=data.get('backstory', ''),
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at', datetime.now()),
            updated_at=datetime.fromisoformat(data['updated_at']) if isinstance(data.get('updated_at'), str) else data.get('updated_at', datetime.now()),
            metadata=data.get('metadata', {})
        )


@dataclass
class PlotPoint:
    """Model representing a plot point in the story."""

    id: str
    project_id: str
    title: str
    description: str = ""
    chapter_number: Optional[int] = None
    plot_type: str = "event"  # event, revelation, conflict, resolution, twist
    importance: int = 1  # 1-5 scale
    characters_involved: List[str] = field(default_factory=list)  # character IDs
    dependencies: List[str] = field(default_factory=list)  # other plot point IDs this depends on
    consequences: List[str] = field(default_factory=list)  # other plot point IDs this leads to
    status: str = "planned"  # planned, written, revised
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'description': self.description,
            'chapter_number': self.chapter_number,
            'plot_type': self.plot_type,
            'importance': self.importance,
            'characters_involved': self.characters_involved,
            'dependencies': self.dependencies,
            'consequences': self.consequences,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlotPoint':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            project_id=data['project_id'],
            title=data['title'],
            description=data.get('description', ''),
            chapter_number=data.get('chapter_number'),
            plot_type=data.get('plot_type', 'event'),
            importance=data.get('importance', 1),
            characters_involved=data.get('characters_involved', []),
            dependencies=data.get('dependencies', []),
            consequences=data.get('consequences', []),
            status=data.get('status', 'planned'),
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at', datetime.now()),
            updated_at=datetime.fromisoformat(data['updated_at']) if isinstance(data.get('updated_at'), str) else data.get('updated_at', datetime.now()),
            metadata=data.get('metadata', {})
        )


@dataclass
class WritingTemplate:
    """Model representing a writing template/preset."""

    id: str
    name: str
    description: str
    genre: str
    system_prompt: str
    outline_template: str = ""
    character_template: str = ""
    chapter_prompt_template: str = ""
    created_by: Optional[str] = None  # user_id or None for system templates
    is_public: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'genre': self.genre,
            'system_prompt': self.system_prompt,
            'outline_template': self.outline_template,
            'character_template': self.character_template,
            'chapter_prompt_template': self.chapter_prompt_template,
            'created_by': self.created_by,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WritingTemplate':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            genre=data.get('genre', 'fiction'),
            system_prompt=data.get('system_prompt', ''),
            outline_template=data.get('outline_template', ''),
            character_template=data.get('character_template', ''),
            chapter_prompt_template=data.get('chapter_prompt_template', ''),
            created_by=data.get('created_by'),
            is_public=data.get('is_public', True),
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at', datetime.now()),
            metadata=data.get('metadata', {})
        )


# Default writing style templates
DEFAULT_WRITING_STYLES = {
    'hemingway': {
        'name': 'Hemingway / Minimalist',
        'description': 'Sparse, direct prose with short sentences. Focus on action and dialogue over description.',
        'system_prompt': 'Write in a minimalist style with short, declarative sentences. Avoid adverbs and excessive description. Focus on action and dialogue. Let subtext carry emotional weight.',
        'traits': ['concise', 'direct', 'action-focused']
    },
    'literary': {
        'name': 'Literary Fiction',
        'description': 'Lyrical, introspective prose with focus on character development and thematic depth.',
        'system_prompt': 'Write with literary precision. Use evocative language, complex sentences, and rich imagery. Focus on character interiority and thematic resonance.',
        'traits': ['lyrical', 'introspective', 'thematic']
    },
    'thriller': {
        'name': 'Thriller / Page-Turner',
        'description': 'Fast-paced, tension-filled prose with short chapters and cliffhangers.',
        'system_prompt': 'Write fast-paced, tension-filled prose. Use short paragraphs and chapter cliffhangers. Focus on pacing and suspense. Every scene should advance the plot.',
        'traits': ['fast-paced', 'tension', 'suspenseful']
    },
    'romance': {
        'name': 'Romance',
        'description': 'Emotional, character-driven prose with focus on relationships and dialogue.',
        'system_prompt': 'Write emotionally engaging romance. Focus on character chemistry and relationship development. Use witty dialogue and emotional introspection. Build tension and satisfying resolution.',
        'traits': ['emotional', 'character-driven', 'dialogue-rich']
    },
    'scifi': {
        'name': 'Science Fiction',
        'description': 'Technical, world-building prose with concepts and ideas at the forefront.',
        'system_prompt': 'Write science fiction with focus on world-building and concepts. Balance technical exposition with character moments. Use clear, precise language for scientific concepts.',
        'traits': ['technical', 'world-building', 'conceptual']
    },
    'fantasy': {
        'name': 'Fantasy Epic',
        'description': 'Rich, immersive prose with detailed world-building and epic scope.',
        'system_prompt': 'Write epic fantasy with rich world-building. Use sensory detail to bring settings to life. Balance action with lore. Create memorable characters with clear motivations.',
        'traits': ['immersive', 'world-building', 'epic']
    },
    'technical': {
        'name': 'Technical / Educational',
        'description': 'Clear, structured prose for educational or technical content.',
        'system_prompt': 'Write clear, structured technical content. Use examples and explanations. Organize information logically. Define technical terms when first introduced.',
        'traits': ['clear', 'structured', 'educational']
    },
    'poetic': {
        'name': 'Poetic / Lyrical',
        'description': 'Beautiful, rhythmic prose with focus on imagery and sound.',
        'system_prompt': 'Write with poetic beauty. Use rhythm, alliteration, and vivid imagery. Let the sound of words enhance meaning. Create passages that reward re-reading.',
        'traits': ['rhythmic', 'imagery-rich', 'beautiful']
    }
}

# Default genre-specific prompts
GENRE_PROMPTS = {
    'fantasy': {
        'system_prompt': """You are writing a fantasy novel. Focus on:
- World-building: Create immersive settings with clear rules for magic, politics, and geography
- Character archetypes with fresh twists on familiar tropes
- Epic scope with multiple storylines converging
- Sensory details that bring the fantastical to life
- Clear power systems and consistent world rules""",
        'outline_guidance': 'Include world-building chapters, character arcs across the narrative, and escalation of stakes.'
    },
    'science_fiction': {
        'system_prompt': """You are writing a science fiction novel. Focus on:
- Plausible scientific concepts extrapolated from current technology
- Social commentary through speculative scenarios
- Clear explanation of technical concepts without infodumping
- Characters grappling with technological change
- Balance between ideas and human drama""",
        'outline_guidance': 'Establish the technological premise early, explore implications, and resolve with both personal and societal stakes.'
    },
    'mystery': {
        'system_prompt': """You are writing a mystery novel. Focus on:
- Fair play: all clues should be available to the reader
- Red herrings and misdirection that don\'t cheat
- Pacing that builds tension toward the reveal
- Character motivations that make sense in retrospect
- A satisfying resolution that recontextualizes earlier events""",
        'outline_guidance': 'Plant clues throughout, ensure the detective has clear methodology, and pace revelations to maintain suspense.'
    },
    'romance': {
        'system_prompt': """You are writing a romance novel. Focus on:
- Chemistry and tension between the leads
- Emotional stakes that feel real and earned
- Dialogue that reveals character and builds connection
- Conflict that comes from character, not arbitrary obstacles
- A satisfying emotional payoff""",
        'outline_guidance': 'Structure around the romance arc: meet-cute, attraction, conflict, growth, and resolution.'
    },
    'thriller': {
        'system_prompt': """You are writing a thriller. Focus on:
- Immediate tension from the opening pages
- Short chapters that end with hooks
- A protagonist with clear, relatable stakes
- Antagonists with comprehensible motivations
- Twists that reframe earlier events without cheating""",
        'outline_guidance': 'Open with a hook, escalate stakes every chapter, and race toward a climactic confrontation.'
    },
    'horror': {
        'system_prompt': """You are writing a horror novel. Focus on:
- Building dread through atmosphere and anticipation
- Characters the reader cares about
- Threat that escalates logically
- Moments of false hope and genuine terror
- A resolution that doesn\'t diminish the threat""",
        'outline_guidance': 'Establish normality, introduce the threat, escalate the danger, and survive the climax.'
    },
    'literary': {
        'system_prompt': """You are writing literary fiction. Focus on:
- Language that rewards close reading
- Characters with psychological depth
- Themes that emerge from character and situation
- Moments of insight and epiphany
- Ambiguity that invites interpretation""",
        'outline_guidance': 'Focus on character development, key turning points, and thematic progression rather than plot machinery.'
    },
    'historical': {
        'system_prompt': """You are writing historical fiction. Focus on:
- Period-appropriate language without excessive archaisms
- Historical accuracy in details and context
- Characters who reflect their era while remaining relatable
- Historical events woven naturally into personal stories
- Research that enriches without overwhelming""",
        'outline_guidance': 'Align personal story with historical timeline, research period details, and honor the historical record.'
    }
}