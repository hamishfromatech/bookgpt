"""
SQLite database utilities for BookGPT application.

Provides persistent storage for book projects, settings, and related data.
"""

import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from models.book_model import BookProject, Chapter, AgentExecution, ProjectStats

logger = logging.getLogger(__name__)

class BookDatabase:
    """Handles SQLite database operations for BookGPT."""
    
    def __init__(self, db_path: str = "data/bookgpt.db"):
        self.db_path = db_path
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
