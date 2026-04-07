"""
SQLite database utilities for BookGPT application.

Provides persistent storage for book projects, settings, and related data.
"""

import sqlite3
import json
import uuid
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from models.book_model import BookProject, Chapter, AgentExecution, ProjectStats

logger = logging.getLogger(__name__)

class BookDatabase:
    """Handles SQLite database operations for BookGPT."""

    def __init__(self, db_path: str = "data/bookgpt.db"):
        self.db_path = db_path
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.init_database()

    def init_database(self):
        """Initialize database tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Projects table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        genre TEXT NOT NULL,
                        target_length INTEGER NOT NULL,
                        writing_style TEXT NOT NULL,
                        status TEXT DEFAULT 'created',
                        outline TEXT,
                        research_materials TEXT,
                        chapters_completed INTEGER DEFAULT 0,
                        total_words INTEGER DEFAULT 0,
                        current_chapter INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP NULL,
                        metadata TEXT DEFAULT '{}'
                    )
                ''')
                
                # Settings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        id TEXT PRIMARY KEY DEFAULT 'default',
                        category TEXT NOT NULL,
                        data TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Chapters table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chapters (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        chapter_number INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT DEFAULT '',
                        word_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'draft',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT DEFAULT '',
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    )
                ''')
                
                # Agent executions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS agent_executions (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        step_type TEXT NOT NULL,
                        input_prompt TEXT NOT NULL,
                        tool_calls TEXT DEFAULT '[]',
                        results TEXT DEFAULT '[]',
                        status TEXT DEFAULT 'pending',
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP NULL,
                        error_message TEXT NULL,
                        execution_time REAL NULL,
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    )
                ''')
                
                # Project stats table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS project_stats (
                        project_id TEXT PRIMARY KEY,
                        total_sessions INTEGER DEFAULT 0,
                        total_agent_steps INTEGER DEFAULT 0,
                        total_files_created INTEGER DEFAULT 0,
                        average_chapter_length REAL DEFAULT 0.0,
                        writing_velocity REAL DEFAULT 0.0,
                        most_productive_hour INTEGER DEFAULT 0,
                        last_activity TIMESTAMP NULL,
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    )
                ''')

                # Chapter versions table - for version history
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chapter_versions (
                        id TEXT PRIMARY KEY,
                        chapter_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        version_number INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        word_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT 'agent',
                        change_summary TEXT DEFAULT '',
                        parent_version_id TEXT,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    )
                ''')

                # Characters table - for character management
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS characters (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        role TEXT DEFAULT '',
                        first_appearance_chapter INTEGER,
                        last_appearance_chapter INTEGER,
                        traits TEXT DEFAULT '[]',
                        relationships TEXT DEFAULT '{}',
                        backstory TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    )
                ''')

                # Plot points table - for plot management
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS plot_points (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        chapter_number INTEGER,
                        plot_type TEXT DEFAULT 'event',
                        importance INTEGER DEFAULT 1,
                        characters_involved TEXT DEFAULT '[]',
                        dependencies TEXT DEFAULT '[]',
                        consequences TEXT DEFAULT '[]',
                        status TEXT DEFAULT 'planned',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    )
                ''')

                # Writing templates table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS writing_templates (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        genre TEXT DEFAULT 'fiction',
                        system_prompt TEXT NOT NULL,
                        outline_template TEXT DEFAULT '',
                        character_template TEXT DEFAULT '',
                        chapter_prompt_template TEXT DEFAULT '',
                        created_by TEXT,
                        is_public INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}'
                    )
                ''')

                # Create additional indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_chapter_versions_project ON chapter_versions(project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_chapter_versions_chapter ON chapter_versions(chapter_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plot_points_project ON plot_points(project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_templates_genre ON writing_templates(genre)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_templates_public ON writing_templates(is_public)')
                
                # Create indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_chapters_project_id ON chapters(project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_executions_project_id ON agent_executions(project_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category)')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def save_project(self, project: BookProject) -> bool:
        """Save a book project to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO projects 
                    (id, user_id, title, genre, target_length, writing_style, status, 
                     outline, research_materials, chapters_completed, total_words, current_chapter,
                     created_at, updated_at, completed_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    project.id,
                    project.user_id,
                    project.title,
                    project.genre,
                    project.target_length,
                    project.writing_style,
                    project.status,
                    json.dumps(project.outline) if project.outline else None,
                    json.dumps(project.research_materials) if project.research_materials else None,
                    project.chapters_completed,
                    project.total_words,
                    project.current_chapter,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                    project.completed_at.isoformat() if project.completed_at else None,
                    json.dumps(project.metadata)
                ))
                
                conn.commit()
                logger.info(f"Project saved: {project.id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving project {project.id}: {e}")
            return False
    
    def get_project(self, project_id: str) -> Optional[BookProject]:
        """Retrieve a book project from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # Parse JSON fields
                outline = json.loads(row['outline']) if row['outline'] else None
                research_materials = json.loads(row['research_materials']) if row['research_materials'] else None
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                
                project = BookProject(
                    id=row['id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    genre=row['genre'],
                    target_length=row['target_length'],
                    writing_style=row['writing_style'],
                    status=row['status'],
                    outline=outline,
                    research_materials=research_materials,
                    chapters_completed=row['chapters_completed'],
                    total_words=row['total_words'],
                    current_chapter=row['current_chapter'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    metadata=metadata
                )
                
                logger.info(f"Project loaded: {project_id}")
                return project
                
        except Exception as e:
            logger.error(f"Error loading project {project_id}: {e}")
            return None
    
    def list_all_projects(self) -> List[Dict[str, Any]]:
        """List all projects with basic information."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, title, genre, status, chapters_completed, total_words,
                           target_length, created_at, updated_at
                    FROM projects
                    ORDER BY updated_at DESC
                ''')

                projects = []
                for row in cursor.fetchall():
                    projects.append({
                        'id': row['id'],
                        'title': row['title'],
                        'genre': row['genre'],
                        'status': row['status'],
                        'chapters_completed': row['chapters_completed'],
                        'total_words': row['total_words'],
                        'target_length': row['target_length'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })

                logger.info(f"Listed {len(projects)} total projects")
                return projects

        except Exception as e:
            logger.error(f"Error listing all projects: {e}")
            return []

    def list_user_projects(self, user_id: str) -> List[Dict[str, Any]]:
        """List all projects for a specific user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, title, genre, status, chapters_completed, total_words,
                           target_length, created_at, updated_at
                    FROM projects
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                ''', (user_id,))

                projects = []
                for row in cursor.fetchall():
                    projects.append({
                        'id': row['id'],
                        'title': row['title'],
                        'genre': row['genre'],
                        'status': row['status'],
                        'chapters_completed': row['chapters_completed'],
                        'total_words': row['total_words'],
                        'target_length': row['target_length'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })

                logger.info(f"Listed {len(projects)} projects for user {user_id}")
                return projects

        except Exception as e:
            logger.error(f"Error listing user projects: {e}")
            return []
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its associated data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete project (cascades will handle related records)
                cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
                
                conn.commit()
                logger.info(f"Project deleted: {project_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False
    
    def save_settings(self, category: str, data: Dict[str, Any]) -> bool:
        """Save settings for a category."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (id, category, data, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (f"{category}_settings", category, json.dumps(data)))
                
                conn.commit()
                logger.info(f"Settings saved for category: {category}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving settings for {category}: {e}")
            return False
    
    def get_settings(self, category: str) -> Optional[Dict[str, Any]]:
        """Get settings for a category."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT data FROM settings WHERE category = ?', (category,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return json.loads(row['data'])
                
        except Exception as e:
            logger.error(f"Error getting settings for {category}: {e}")
            return None
    
    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings categories."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('SELECT category, data FROM settings')
                rows = cursor.fetchall()
                
                settings = {}
                for row in rows:
                    settings[row['category']] = json.loads(row['data'])
                
                return settings
                
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return {}
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {
                    'total_projects': 0,
                    'total_chapters': 0,
                    'total_executions': 0,
                    'storage_size_mb': 0,
                    'oldest_project': None,
                    'newest_project': None
                }
                
                # Count projects
                cursor.execute('SELECT COUNT(*) FROM projects')
                stats['total_projects'] = cursor.fetchone()[0]
                
                # Count chapters
                cursor.execute('SELECT COUNT(*) FROM chapters')
                stats['total_chapters'] = cursor.fetchone()[0]
                
                # Count executions
                cursor.execute('SELECT COUNT(*) FROM agent_executions')
                stats['total_executions'] = cursor.fetchone()[0]
                
                # Find oldest and newest projects
                cursor.execute('''
                    SELECT id, title, created_at FROM projects 
                    ORDER BY created_at ASC LIMIT 1
                ''')
                oldest = cursor.fetchone()
                if oldest:
                    stats['oldest_project'] = {'id': oldest[0], 'title': oldest[1], 'created_at': oldest[2]}
                
                cursor.execute('''
                    SELECT id, title, created_at FROM projects 
                    ORDER BY created_at DESC LIMIT 1
                ''')
                newest = cursor.fetchone()
                if newest:
                    stats['newest_project'] = {'id': newest[0], 'title': newest[1], 'created_at': newest[2]}
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}

    # =========================================================================
    # Chapter Version History Methods
    # =========================================================================

    def save_chapter_version(self, chapter_id: str, project_id: str, content: str,
                             created_by: str = 'agent', change_summary: str = '',
                             parent_version_id: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Save a new version of a chapter."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get next version number
                cursor.execute('''
                    SELECT MAX(version_number) FROM chapter_versions
                    WHERE chapter_id = ? AND project_id = ?
                ''', (chapter_id, project_id))
                result = cursor.fetchone()
                next_version = (result[0] or 0) + 1

                version_id = str(uuid.uuid4())
                word_count = len(content.split())

                cursor.execute('''
                    INSERT INTO chapter_versions
                    (id, chapter_id, project_id, version_number, content, word_count,
                     created_by, change_summary, parent_version_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (version_id, chapter_id, project_id, next_version, content, word_count,
                      created_by, change_summary, parent_version_id, json.dumps(metadata or {})))

                conn.commit()
                logger.info(f"Saved chapter version {next_version} for chapter {chapter_id}")

                return {
                    'id': version_id,
                    'chapter_id': chapter_id,
                    'project_id': project_id,
                    'version_number': next_version,
                    'word_count': word_count
                }

        except Exception as e:
            logger.error(f"Error saving chapter version: {e}")
            return {'error': str(e)}

    def get_chapter_versions(self, chapter_id: str, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all versions of a chapter."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, chapter_id, project_id, version_number, word_count,
                           created_at, created_by, change_summary, parent_version_id
                    FROM chapter_versions
                    WHERE chapter_id = ? AND project_id = ?
                    ORDER BY version_number DESC
                    LIMIT ?
                ''', (chapter_id, project_id, limit))

                versions = []
                for row in cursor.fetchall():
                    versions.append({
                        'id': row['id'],
                        'chapter_id': row['chapter_id'],
                        'project_id': row['project_id'],
                        'version_number': row['version_number'],
                        'word_count': row['word_count'],
                        'created_at': row['created_at'],
                        'created_by': row['created_by'],
                        'change_summary': row['change_summary'],
                        'parent_version_id': row['parent_version_id']
                    })

                return versions

        except Exception as e:
            logger.error(f"Error getting chapter versions: {e}")
            return []

    def get_chapter_version_content(self, version_id: str) -> Optional[str]:
        """Get the content of a specific chapter version."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT content FROM chapter_versions WHERE id = ?', (version_id,))
                result = cursor.fetchone()

                return result[0] if result else None

        except Exception as e:
            logger.error(f"Error getting chapter version content: {e}")
            return None

    def restore_chapter_version(self, chapter_id: str, project_id: str, version_number: int) -> bool:
        """Restore a chapter to a specific version."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT content FROM chapter_versions
                    WHERE chapter_id = ? AND project_id = ? AND version_number = ?
                ''', (chapter_id, project_id, version_number))

                result = cursor.fetchone()
                if not result:
                    return False

                content = result[0]

                # Save as new version
                self.save_chapter_version(
                    chapter_id=chapter_id,
                    project_id=project_id,
                    content=content,
                    created_by='user',
                    change_summary=f'Restored from version {version_number}'
                )

                return True

        except Exception as e:
            logger.error(f"Error restoring chapter version: {e}")
            return False

    # =========================================================================
    # Character Management Methods
    # =========================================================================

    def save_character(self, character_data: Dict[str, Any]) -> str:
        """Save or update a character."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                char_id = character_data.get('id') or str(uuid.uuid4())
                now = datetime.now().isoformat()

                cursor.execute('''
                    INSERT OR REPLACE INTO characters
                    (id, project_id, name, description, role, first_appearance_chapter,
                     last_appearance_chapter, traits, relationships, backstory,
                     updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (char_id, character_data['project_id'], character_data['name'],
                      character_data.get('description', ''), character_data.get('role', ''),
                      character_data.get('first_appearance_chapter'),
                      character_data.get('last_appearance_chapter'),
                      json.dumps(character_data.get('traits', [])),
                      json.dumps(character_data.get('relationships', {})),
                      character_data.get('backstory', ''), now,
                      json.dumps(character_data.get('metadata', {}))))

                conn.commit()
                logger.info(f"Saved character {char_id}")
                return char_id

        except Exception as e:
            logger.error(f"Error saving character: {e}")
            raise

    def get_characters(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all characters for a project."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, project_id, name, description, role,
                           first_appearance_chapter, last_appearance_chapter,
                           traits, relationships, backstory, created_at, updated_at
                    FROM characters WHERE project_id = ?
                    ORDER BY name
                ''', (project_id,))

                characters = []
                for row in cursor.fetchall():
                    characters.append({
                        'id': row['id'],
                        'project_id': row['project_id'],
                        'name': row['name'],
                        'description': row['description'],
                        'role': row['role'],
                        'first_appearance_chapter': row['first_appearance_chapter'],
                        'last_appearance_chapter': row['last_appearance_chapter'],
                        'traits': json.loads(row['traits']),
                        'relationships': json.loads(row['relationships']),
                        'backstory': row['backstory'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })

                return characters

        except Exception as e:
            logger.error(f"Error getting characters: {e}")
            return []

    def delete_character(self, character_id: str) -> bool:
        """Delete a character."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM characters WHERE id = ?', (character_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting character: {e}")
            return False

    # =========================================================================
    # Plot Point Management Methods
    # =========================================================================

    def save_plot_point(self, plot_data: Dict[str, Any]) -> str:
        """Save or update a plot point."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                plot_id = plot_data.get('id') or str(uuid.uuid4())
                now = datetime.now().isoformat()

                cursor.execute('''
                    INSERT OR REPLACE INTO plot_points
                    (id, project_id, title, description, chapter_number, plot_type,
                     importance, characters_involved, dependencies, consequences,
                     status, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (plot_id, plot_data['project_id'], plot_data['title'],
                      plot_data.get('description', ''), plot_data.get('chapter_number'),
                      plot_data.get('plot_type', 'event'), plot_data.get('importance', 1),
                      json.dumps(plot_data.get('characters_involved', [])),
                      json.dumps(plot_data.get('dependencies', [])),
                      json.dumps(plot_data.get('consequences', [])),
                      plot_data.get('status', 'planned'), now,
                      json.dumps(plot_data.get('metadata', {}))))

                conn.commit()
                logger.info(f"Saved plot point {plot_id}")
                return plot_id

        except Exception as e:
            logger.error(f"Error saving plot point: {e}")
            raise

    def get_plot_points(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all plot points for a project."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, project_id, title, description, chapter_number, plot_type,
                           importance, characters_involved, dependencies, consequences,
                           status, created_at, updated_at
                    FROM plot_points WHERE project_id = ?
                    ORDER BY chapter_number, importance DESC
                ''', (project_id,))

                plots = []
                for row in cursor.fetchall():
                    plots.append({
                        'id': row['id'],
                        'project_id': row['project_id'],
                        'title': row['title'],
                        'description': row['description'],
                        'chapter_number': row['chapter_number'],
                        'plot_type': row['plot_type'],
                        'importance': row['importance'],
                        'characters_involved': json.loads(row['characters_involved']),
                        'dependencies': json.loads(row['dependencies']),
                        'consequences': json.loads(row['consequences']),
                        'status': row['status'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    })

                return plots

        except Exception as e:
            logger.error(f"Error getting plot points: {e}")
            return []

    def delete_plot_point(self, plot_id: str) -> bool:
        """Delete a plot point."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM plot_points WHERE id = ?', (plot_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting plot point: {e}")
            return False

    # =========================================================================
    # Writing Templates Methods
    # =========================================================================

    def save_template(self, template_data: Dict[str, Any]) -> str:
        """Save or update a writing template."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                template_id = template_data.get('id') or str(uuid.uuid4())

                cursor.execute('''
                    INSERT OR REPLACE INTO writing_templates
                    (id, name, description, genre, system_prompt, outline_template,
                     character_template, chapter_prompt_template, created_by, is_public, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (template_id, template_data['name'], template_data.get('description', ''),
                      template_data.get('genre', 'fiction'), template_data['system_prompt'],
                      template_data.get('outline_template', ''),
                      template_data.get('character_template', ''),
                      template_data.get('chapter_prompt_template', ''),
                      template_data.get('created_by'), template_data.get('is_public', True),
                      json.dumps(template_data.get('metadata', {}))))

                conn.commit()
                logger.info(f"Saved template {template_id}")
                return template_id

        except Exception as e:
            logger.error(f"Error saving template: {e}")
            raise

    def get_templates(self, genre: str = None, include_private: bool = False,
                      user_id: str = None) -> List[Dict[str, Any]]:
        """Get writing templates, optionally filtered by genre."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if genre:
                    if include_private and user_id:
                        cursor.execute('''
                            SELECT * FROM writing_templates
                            WHERE genre = ? AND (is_public = 1 OR created_by = ?)
                            ORDER BY name
                        ''', (genre, user_id))
                    else:
                        cursor.execute('''
                            SELECT * FROM writing_templates WHERE genre = ? AND is_public = 1
                            ORDER BY name
                        ''', (genre,))
                else:
                    if include_private and user_id:
                        cursor.execute('''
                            SELECT * FROM writing_templates
                            WHERE is_public = 1 OR created_by = ?
                            ORDER BY name
                        ''', (user_id,))
                    else:
                        cursor.execute('''
                            SELECT * FROM writing_templates WHERE is_public = 1 ORDER BY name
                        ''')

                templates = []
                for row in cursor.fetchall():
                    templates.append({
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'],
                        'genre': row['genre'],
                        'system_prompt': row['system_prompt'],
                        'outline_template': row['outline_template'],
                        'character_template': row['character_template'],
                        'chapter_prompt_template': row['chapter_prompt_template'],
                        'created_by': row['created_by'],
                        'is_public': row['is_public'],
                        'created_at': row['created_at'],
                        'metadata': json.loads(row['metadata'])
                    })

                return templates

        except Exception as e:
            logger.error(f"Error getting templates: {e}")
            return []

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific template by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM writing_templates WHERE id = ?', (template_id,))
                row = cursor.fetchone()

                if row:
                    return {
                        'id': row['id'],
                        'name': row['name'],
                        'description': row['description'],
                        'genre': row['genre'],
                        'system_prompt': row['system_prompt'],
                        'outline_template': row['outline_template'],
                        'character_template': row['character_template'],
                        'chapter_prompt_template': row['chapter_prompt_template'],
                        'created_by': row['created_by'],
                        'is_public': row['is_public'],
                        'created_at': row['created_at'],
                        'metadata': json.loads(row['metadata'])
                    }

                return None

        except Exception as e:
            logger.error(f"Error getting template: {e}")
            return None
