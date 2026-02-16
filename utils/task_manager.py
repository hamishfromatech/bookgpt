"""
Background task manager for BookGPT application.

Handles asynchronous book writing processes without blocking the main application.
"""

import threading
import queue
import uuid
import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    """Represents a background task."""
    id: str
    type: str
    project_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    current_phase: str = "initializing"
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    activities: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'type': self.type,
            'project_id': self.project_id,
            'status': self.status.value,
            'progress': self.progress,
            'current_phase': self.current_phase,
            'message': self.message,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'activities': self.activities
        }

class TaskManager:
    """Manages background tasks for async processing."""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.task_queue = queue.Queue()
        self.worker_threads = []
        self.max_workers = 3  # Limit concurrent background tasks
        self.running = True
        self._start_workers()
    
    def _start_workers(self):
        """Start worker threads for processing tasks."""
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker, name=f"TaskWorker-{i}")
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)
            logger.info(f"Started worker thread: {worker.name}")
    
    def _worker(self):
        """Worker thread that processes tasks from the queue."""
        logger.info(f"Worker thread {threading.current_thread().name} started")
        while self.running:
            try:
                task_id = self.task_queue.get(timeout=1.0)
                if task_id is None:
                    continue
                
                task = self.tasks.get(task_id)
                if not task:
                    logger.warning(f"Task {task_id} not found in tasks dict")
                    continue
                
                logger.info(f"Worker processing task {task_id} with status {task.status.value}")
                self._execute_task(task)
                
                self.task_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker thread error: {e}")
                import traceback
                logger.error(f"Worker traceback: {traceback.format_exc()}")
        
        logger.info(f"Worker thread {threading.current_thread().name} stopped")
    
    def _execute_task(self, task: Task):
        """Execute a single task."""
        if not task:
            return
        
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            logger.info(f"Starting task {task.id} of type {task.type}")
            
            # Execute task based on type
            if task.type == 'write_book':
                # Import here to avoid circular imports
                from utils.agent_factory import get_agent
                
                # Get project details - use the same database as the main app
                from utils.database import BookDatabase
                db = BookDatabase()
                project = db.get_project(task.project_id)
                
                if not project:
                    logger.error(f"Project {task.project_id} not found in database")
                    raise Exception(f"Project {task.project_id} not found")
                
                logger.info(f"Found project {task.project_id}: {project.title}")
                
                # Get global agent instance
                agent = get_agent()
                
                # Update project status to writing
                project.status = 'writing'
                project.updated_at = datetime.now()
                db.save_project(project)
                logger.info(f"Updated project {task.project_id} status to writing")
                
                self._execute_book_writing(task, agent, project)
                
                # Update project status on completion
                if task.status == TaskStatus.COMPLETED:
                    project.status = 'completed'
                    project.completed_at = datetime.now()
                elif task.status == TaskStatus.FAILED:
                    project.status = 'failed'
                project.updated_at = datetime.now()
                db.save_project(project)
                
            else:
                raise Exception(f"Unknown task type: {task.type}")
            
            # Only mark as completed if not already failed
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.message = "Task completed successfully"
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.message = f"Task failed: {str(e)}"
            task.completed_at = datetime.now()
            logger.error(f"Task {task.id} failed: {e}")
            import traceback
            logger.error(f"Task failure traceback: {traceback.format_exc()}")
            
            # Update project status to failed
            try:
                from utils.database import BookDatabase
                db = BookDatabase()
                project = db.get_project(task.project_id)
                if project:
                    project.status = 'failed'
                    project.updated_at = datetime.now()
                    db.save_project(project)
                    logger.info(f"Updated project {task.project_id} status to failed")
            except Exception as project_error:
                logger.error(f"Failed to update project status: {project_error}")
        
        finally:
            # Notify completion
            self._notify_task_completion(task)
    
    def _execute_book_writing(self, task: Task, agent, project):
        """Execute book writing task with progress tracking."""
        project_id = task.project_id
        
        # Override agent's progress callback to update task
        def progress_callback(phase: str, progress: float, message: str, activity: str = None):
            task.progress = progress
            task.current_phase = phase
            task.message = message
            
            if activity:
                task.activities.append({
                    'timestamp': datetime.now().isoformat(),
                    'message': activity
                })
            
            # Limit activities to last 50 to prevent memory issues
            if len(task.activities) > 50:
                task.activities = task.activities[-50:]
        
        # Set progress callback
        agent.set_progress_callback(progress_callback)
        
        # Execute the writing process
        result = agent.start_writing_process(project)
        
        task.result = result
        task.progress = 100.0
        task.current_phase = "refining"
        task.message = "Book writing completed successfully. Entering Agent Mode."
    
    def _notify_task_completion(self, task: Task):
        """Notify about task completion (could be extended with websockets, etc.)."""
        logger.info(f"Task {task.id} completed with status: {task.status.value}")
    
    def create_task(self, task_type: str, project_id: str) -> str:
        """Create a new background task."""
        task_id = str(uuid.uuid4())
        
        task = Task(
            id=task_id,
            type=task_type,
            project_id=project_id,
            message=f"Queued {task_type} task..."
        )
        
        self.tasks[task_id] = task
        self.task_queue.put(task_id)
        
        logger.info(f"Created task {task_id} of type {task_type} for project {project_id}")
        logger.info(f"Total tasks in manager: {len(self.tasks)}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_project_tasks(self, project_id: str) -> list:
        """Get all tasks for a project."""
        tasks = [task for task in self.tasks.values() if task.project_id == project_id]
        logger.info(f"Getting tasks for project {project_id}: found {len(tasks)} tasks")
        for task in tasks:
            logger.info(f"  Task {task.id}: type={task.type}, status={task.status.value}")
        return tasks
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task (if it hasn't started yet)."""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.message = "Task cancelled"
            return True
        return False
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed tasks to prevent memory leaks."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                task.completed_at and task.completed_at.timestamp() < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
            logger.info(f"Cleaned up old task: {task_id}")
    
    def shutdown(self):
        """Shutdown the task manager."""
        self.running = False
        
        # Send None to all workers to stop them
        for _ in range(len(self.worker_threads)):
            self.task_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.worker_threads:
            worker.join(timeout=5.0)
        
        logger.info("Task manager shutdown complete")

# Global task manager instance
task_manager = TaskManager()
