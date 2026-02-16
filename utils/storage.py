"""
Storage utilities for BookGPT application.

Provides persistent storage for book projects, chapters, and agent execution data.
"""

import os
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from models.book_model import BookProject, Chapter, AgentExecution, ProjectStats

logger = logging.getLogger(__name__)

class BookStorage:
    """Handles persistent storage for BookGPT projects."""
    
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = storage_dir
        self.ensure_storage_dirs()
    
    def ensure_storage_dirs(self):
        """Create necessary storage directories."""
        dirs = [
            self.storage_dir,
            f"{self.storage_dir}/projects",
            f"{self.storage_dir}/chapters",
            f"{self.storage_dir}/executions",
            f"{self.storage_dir}/stats"
        ]
        
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
    
    def save_project(self, project: BookProject) -> bool:
        """Save a book project to storage."""
        try:
            project_file = f"{self.storage_dir}/projects/{project.id}.json"
            
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Project saved: {project.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving project {project.id}: {e}")
            return False
    
    def get_project(self, project_id: str) -> Optional[BookProject]:
        """Retrieve a book project from storage."""
        try:
            project_file = f"{self.storage_dir}/projects/{project_id}.json"
            
            if not os.path.exists(project_file):
                return None
            
            with open(project_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            project = BookProject.from_dict(data)
            logger.info(f"Project loaded: {project_id}")
            return project
            
        except Exception as e:
            logger.error(f"Error loading project {project_id}: {e}")
            return None
    
    def get_user_projects(self, user_id: str) -> List[BookProject]:
        """Get all projects for a specific user."""
        try:
            projects = []
            projects_dir = f"{self.storage_dir}/projects"
            
            if not os.path.exists(projects_dir):
                return projects
            
            for filename in os.listdir(projects_dir):
                if filename.endswith('.json'):
                    project_file = os.path.join(projects_dir, filename)
                    
                    try:
                        with open(project_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        if data.get('user_id') == user_id:
                            project = BookProject.from_dict(data)
                            projects.append(project)
                            
                    except Exception as e:
                        logger.warning(f"Error loading project file {filename}: {e}")
            
            # Sort by updated_at descending
            projects.sort(key=lambda p: p.updated_at, reverse=True)
            
            logger.info(f"Found {len(projects)} projects for user {user_id}")
            return projects
            
        except Exception as e:
            logger.error(f"Error getting user projects: {e}")
            return []
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its associated files."""
        try:
            # Delete project file
            project_file = f"{self.storage_dir}/projects/{project_id}.json"
            if os.path.exists(project_file):
                os.remove(project_file)
            
            # Delete project directory and all contents
            project_dir = f"{self.storage_dir}/projects/{project_id}"
            if os.path.exists(project_dir):
                import shutil
                shutil.rmtree(project_dir)
            
            # Delete associated chapters
            chapters_dir = f"{self.storage_dir}/chapters/{project_id}"
            if os.path.exists(chapters_dir):
                import shutil
                shutil.rmtree(chapters_dir)
            
            # Delete associated executions
            exec_dir = f"{self.storage_dir}/executions/{project_id}"
            if os.path.exists(exec_dir):
                import shutil
                shutil.rmtree(exec_dir)
            
            logger.info(f"Project deleted: {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False
    
    def save_chapter(self, chapter: Chapter) -> bool:
        """Save a chapter to storage."""
        try:
            # Ensure chapter directory exists
            chapter_dir = f"{self.storage_dir}/chapters/{chapter.project_id}"
            os.makedirs(chapter_dir, exist_ok=True)
            
            chapter_file = f"{chapter_dir}/chapter_{chapter.chapter_number}.json"
            
            with open(chapter_file, 'w', encoding='utf-8') as f:
                json.dump(chapter.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Chapter saved: {chapter.project_id} - Chapter {chapter.chapter_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving chapter {chapter.id}: {e}")
            return False
    
    def get_chapter(self, project_id: str, chapter_number: int) -> Optional[Chapter]:
        """Retrieve a specific chapter."""
        try:
            chapter_file = f"{self.storage_dir}/chapters/{project_id}/chapter_{chapter_number}.json"
            
            if not os.path.exists(chapter_file):
                return None
            
            with open(chapter_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            chapter = Chapter.from_dict(data)
            logger.info(f"Chapter loaded: {project_id} - Chapter {chapter_number}")
            return chapter
            
        except Exception as e:
            logger.error(f"Error loading chapter {project_id} - {chapter_number}: {e}")
            return None
    
    def get_project_chapters(self, project_id: str) -> List[Chapter]:
        """Get all chapters for a project."""
        try:
            chapters = []
            chapters_dir = f"{self.storage_dir}/chapters/{project_id}"
            
            if not os.path.exists(chapters_dir):
                return chapters
            
            for filename in os.listdir(chapters_dir):
                if filename.startswith('chapter_') and filename.endswith('.json'):
                    chapter_file = os.path.join(chapters_dir, filename)
                    
                    try:
                        with open(chapter_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        chapter = Chapter.from_dict(data)
                        chapters.append(chapter)
                        
                    except Exception as e:
                        logger.warning(f"Error loading chapter file {filename}: {e}")
            
            # Sort by chapter number
            chapters.sort(key=lambda c: c.chapter_number)
            
            logger.info(f"Found {len(chapters)} chapters for project {project_id}")
            return chapters
            
        except Exception as e:
            logger.error(f"Error getting project chapters: {e}")
            return []
    
    def save_execution(self, execution: AgentExecution) -> bool:
        """Save an agent execution record."""
        try:
            # Ensure execution directory exists
            exec_dir = f"{self.storage_dir}/executions/{execution.project_id}"
            os.makedirs(exec_dir, exist_ok=True)
            
            exec_file = f"{exec_dir}/{execution.id}.json"
            
            with open(exec_file, 'w', encoding='utf-8') as f:
                json.dump(execution.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Execution saved: {execution.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving execution {execution.id}: {e}")
            return False
    
    def get_project_executions(self, project_id: str) -> List[AgentExecution]:
        """Get all executions for a project."""
        try:
            executions = []
            exec_dir = f"{self.storage_dir}/executions/{project_id}"
            
            if not os.path.exists(exec_dir):
                return executions
            
            for filename in os.listdir(exec_dir):
                if filename.endswith('.json'):
                    exec_file = os.path.join(exec_dir, filename)
                    
                    try:
                        with open(exec_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        execution = AgentExecution.from_dict(data)
                        executions.append(execution)
                        
                    except Exception as e:
                        logger.warning(f"Error loading execution file {filename}: {e}")
            
            # Sort by started_at descending
            executions.sort(key=lambda e: e.started_at, reverse=True)
            
            logger.info(f"Found {len(executions)} executions for project {project_id}")
            return executions
            
        except Exception as e:
            logger.error(f"Error getting project executions: {e}")
            return []
    
    def save_stats(self, stats: ProjectStats) -> bool:
        """Save project statistics."""
        try:
            stats_file = f"{self.storage_dir}/stats/{stats.project_id}.json"
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Stats saved: {stats.project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving stats {stats.project_id}: {e}")
            return False
    
    def get_stats(self, project_id: str) -> Optional[ProjectStats]:
        """Retrieve project statistics."""
        try:
            stats_file = f"{self.storage_dir}/stats/{project_id}.json"
            
            if not os.path.exists(stats_file):
                # Create default stats
                stats = ProjectStats(project_id=project_id)
                self.save_stats(stats)
                return stats
            
            with open(stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stats = ProjectStats.from_dict(data)
            logger.info(f"Stats loaded: {project_id}")
            return stats
            
        except Exception as e:
            logger.error(f"Error loading stats {project_id}: {e}")
            return None
    
    def list_all_projects(self) -> List[Dict[str, Any]]:
        """List all projects with basic information."""
        try:
            projects = []
            projects_dir = f"{self.storage_dir}/projects"
            
            if not os.path.exists(projects_dir):
                return projects
            
            for filename in os.listdir(projects_dir):
                if filename.endswith('.json'):
                    project_file = os.path.join(projects_dir, filename)
                    
                    try:
                        with open(project_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # Include only basic project info
                        projects.append({
                            'id': data.get('id'),
                            'title': data.get('title'),
                            'genre': data.get('genre'),
                            'status': data.get('status'),
                            'chapters_completed': data.get('chapters_completed', 0),
                            'total_words': data.get('total_words', 0),
                            'target_length': data.get('target_length', 0),
                            'created_at': data.get('created_at'),
                            'updated_at': data.get('updated_at')
                        })
                        
                    except Exception as e:
                        logger.warning(f"Error loading project file {filename}: {e}")
            
            # Sort by updated_at descending
            projects.sort(key=lambda p: p.get('updated_at', ''), reverse=True)
            
            logger.info(f"Listed {len(projects)} total projects")
            return projects
            
        except Exception as e:
            logger.error(f"Error listing all projects: {e}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            stats = {
                'total_projects': 0,
                'total_chapters': 0,
                'total_executions': 0,
                'storage_size_mb': 0,
                'oldest_project': None,
                'newest_project': None
            }
            
            # Count projects
            projects_dir = f"{self.storage_dir}/projects"
            if os.path.exists(projects_dir):
                project_files = [f for f in os.listdir(projects_dir) if f.endswith('.json')]
                stats['total_projects'] = len(project_files)
            
            # Count chapters
            chapters_dir = f"{self.storage_dir}/chapters"
            if os.path.exists(chapters_dir):
                chapter_count = 0
                for project_dir in os.listdir(chapters_dir):
                    project_chapters_dir = os.path.join(chapters_dir, project_dir)
                    if os.path.isdir(project_chapters_dir):
                        chapter_count += len([f for f in os.listdir(project_chapters_dir) 
                                            if f.startswith('chapter_') and f.endswith('.json')])
                stats['total_chapters'] = chapter_count
            
            # Count executions
            exec_dir = f"{self.storage_dir}/executions"
            if os.path.exists(exec_dir):
                exec_count = 0
                for project_dir in os.listdir(exec_dir):
                    project_exec_dir = os.path.join(exec_dir, project_dir)
                    if os.path.isdir(project_exec_dir):
                        exec_count += len([f for f in os.listdir(project_exec_dir) 
                                         if f.endswith('.json')])
                stats['total_executions'] = exec_count
            
            # Calculate storage size
            total_size = 0
            for root, dirs, files in os.walk(self.storage_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            stats['storage_size_mb'] = round(total_size / (1024 * 1024), 2)
            
            # Find oldest and newest projects
            all_projects = self.list_all_projects()
            if all_projects:
                stats['oldest_project'] = min(all_projects, key=lambda p: p.get('created_at', ''))
                stats['newest_project'] = max(all_projects, key=lambda p: p.get('created_at', ''))
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}