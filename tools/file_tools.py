"""
File Tools for BookGPT Agent.

Professional file operation tools modeled after coding agents like Cursor, Windsurf, 
Aider, and OpenAI Codex. These tools provide:

1. File Reading - Read entire files or specific line ranges
2. File Writing - Create new files or overwrite existing ones
3. File Editing - Search and replace, or apply diffs
4. Directory Listing - List files and directories
5. File Search - Search for files by name/pattern
6. Content Search - Search for content within files (grep-style)

All tools follow the OpenAI function calling schema pattern.
"""

import os
import re
import glob
import fnmatch
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Base directory for all book projects
PROJECTS_BASE_DIR = "projects"

# Directories to always ignore
IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', 
               '.env', 'dist', 'build', '.idea', '.vscode', '.cache'}

# File patterns to ignore
IGNORE_PATTERNS = {'*.pyc', '*.pyo', '.DS_Store', '*.swp', '*.swo', 'Thumbs.db'}


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def description(self) -> str:
        pass
    
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        pass


def get_project_path(project_id: str) -> str:
    """Get the base path for a project."""
    return os.path.join(PROJECTS_BASE_DIR, project_id)


def resolve_path(project_id: str, relative_path: str) -> str:
    """Resolve a relative path to an absolute path within the project."""
    base_path = get_project_path(project_id)
    # Normalize and join paths
    full_path = os.path.normpath(os.path.join(base_path, relative_path))
    
    # Security check: ensure the path is within the project directory
    if not full_path.startswith(os.path.normpath(base_path)):
        raise ValueError(f"Path '{relative_path}' escapes project directory")
    
    return full_path


def should_ignore(path: str) -> bool:
    """Check if a path should be ignored."""
    basename = os.path.basename(path)
    
    # Check directory ignores
    if basename in IGNORE_DIRS:
        return True
    
    # Check file pattern ignores
    for pattern in IGNORE_PATTERNS:
        if fnmatch.fnmatch(basename, pattern):
            return True
    
    return False


# =============================================================================
# READ FILE TOOL
# =============================================================================

class ReadFileTool(BaseTool):
    """
    Read content from a file.
    
    Supports:
    - Reading entire files
    - Reading specific line ranges
    - Automatic truncation for large files
    
    Based on Cursor/RooCode read_file tool patterns.
    """
    
    MAX_LINES = 500  # Maximum lines to return without explicit range
    
    def name(self) -> str:
        return "read_file"
    
    def description(self) -> str:
        return """Read content from a file. Can read the entire file or a specific line range.
For large files, content is automatically truncated. Use start_line and end_line 
for precise control over which lines to read."""
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to read, relative to project root"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed). Optional."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (1-indexed, inclusive). Optional."
                }
            },
            "required": ["project_id", "path"]
        }
    
    def execute(
        self, 
        project_id: str, 
        path: str, 
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Read content from a file.
        
        Args:
            project_id: The book project identifier
            path: Path to the file relative to project root
            start_line: Optional starting line (1-indexed)
            end_line: Optional ending line (1-indexed, inclusive)
            
        Returns:
            Dict with file content and metadata
        """
        try:
            full_path = resolve_path(project_id, path)
            
            if not os.path.exists(full_path):
                return {
                    'success': False,
                    'error': f"File not found: {path}"
                }
            
            if not os.path.isfile(full_path):
                return {
                    'success': False,
                    'error': f"Path is not a file: {path}"
                }
            
            # Read file content
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            truncated = False
            
            # Handle line range
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else total_lines
                
                # Clamp to valid range
                start_idx = max(0, min(start_idx, total_lines))
                end_idx = max(0, min(end_idx, total_lines))
                
                selected_lines = lines[start_idx:end_idx]
                actual_start = start_idx + 1
                actual_end = start_idx + len(selected_lines)
            else:
                # No range specified - apply truncation if needed
                if total_lines > self.MAX_LINES:
                    selected_lines = lines[:self.MAX_LINES]
                    truncated = True
                    actual_start = 1
                    actual_end = self.MAX_LINES
                else:
                    selected_lines = lines
                    actual_start = 1
                    actual_end = total_lines
            
            # Format content with line numbers
            numbered_lines = []
            for i, line in enumerate(selected_lines, start=actual_start):
                # Remove trailing newline for cleaner output
                line_content = line.rstrip('\n\r')
                numbered_lines.append(f"{i:4d} | {line_content}")
            
            content = '\n'.join(numbered_lines)
            
            # Add context markers
            result_content = ""
            if actual_start > 1:
                result_content += f"[Lines 1-{actual_start-1} not shown]\n"
            
            result_content += content
            
            if truncated:
                result_content += f"\n\n[Truncated: showing {self.MAX_LINES} of {total_lines} lines. Use start_line/end_line for more.]"
            elif actual_end < total_lines:
                result_content += f"\n[Lines {actual_end+1}-{total_lines} not shown]"
            
            logger.info(f"Read file: {path} (lines {actual_start}-{actual_end} of {total_lines})")
            
            return {
                'success': True,
                'path': path,
                'content': result_content,
                'total_lines': total_lines,
                'lines_returned': len(selected_lines),
                'start_line': actual_start,
                'end_line': actual_end,
                'truncated': truncated
            }
            
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# =============================================================================
# WRITE FILE TOOL
# =============================================================================

class WriteFileTool(BaseTool):
    """
    Write content to a file.
    
    Creates the file if it doesn't exist, or overwrites if it does.
    Automatically creates parent directories as needed.
    
    Based on RooCode write_to_file tool patterns.
    """
    
    def name(self) -> str:
        return "write_file"
    
    def description(self) -> str:
        return """Write content to a file. Creates the file if it doesn't exist, 
or completely overwrites it if it does. Parent directories are created automatically."""
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to write, relative to project root"
                },
                "content": {
                    "type": "string",
                    "description": "The complete content to write to the file"
                }
            },
            "required": ["project_id", "path", "content"]
        }
    
    def execute(
        self, 
        project_id: str, 
        path: str, 
        content: str
    ) -> Dict[str, Any]:
        """
        Write content to a file.
        
        Args:
            project_id: The book project identifier
            path: Path to the file relative to project root
            content: Content to write
            
        Returns:
            Dict with operation result
        """
        try:
            full_path = resolve_path(project_id, path)
            
            # Create parent directories if needed
            parent_dir = os.path.dirname(full_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            # Check if file exists (for logging)
            file_existed = os.path.exists(full_path)
            
            # Write content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Calculate stats
            line_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            char_count = len(content)
            
            action = "Updated" if file_existed else "Created"
            logger.info(f"{action} file: {path} ({line_count} lines, {char_count} chars)")
            
            return {
                'success': True,
                'path': path,
                'action': action.lower(),
                'lines': line_count,
                'characters': char_count,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# =============================================================================
# EDIT FILE TOOL (Search & Replace)
# =============================================================================

class EditFileTool(BaseTool):
    """
    Edit a file using search and replace.
    
    Supports:
    - Literal string replacement
    - Regular expression replacement
    - Case-insensitive search
    - Replace first occurrence or all occurrences
    - Line range restriction
    
    Based on RooCode search_and_replace and Aider diff patterns.
    """
    
    def name(self) -> str:
        return "edit_file"
    
    def description(self) -> str:
        return """Edit a file by searching for text and replacing it. Supports literal strings 
or regex patterns. Can replace first occurrence only or all occurrences."""
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit, relative to project root"
                },
                "search": {
                    "type": "string",
                    "description": "The text or regex pattern to search for"
                },
                "replace": {
                    "type": "string",
                    "description": "The replacement text"
                },
                "use_regex": {
                    "type": "boolean",
                    "description": "Whether to treat search as a regex pattern (default: false)"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: true)"
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default: false)"
                }
            },
            "required": ["project_id", "path", "search", "replace"]
        }
    
    def execute(
        self, 
        project_id: str, 
        path: str, 
        search: str,
        replace: str,
        use_regex: bool = False,
        replace_all: bool = True,
        ignore_case: bool = False
    ) -> Dict[str, Any]:
        """
        Edit a file using search and replace.
        
        Args:
            project_id: The book project identifier
            path: Path to the file relative to project root
            search: Text or pattern to search for
            replace: Replacement text
            use_regex: Treat search as regex
            replace_all: Replace all occurrences
            ignore_case: Case-insensitive search
            
        Returns:
            Dict with operation result and diff
        """
        try:
            full_path = resolve_path(project_id, path)
            
            if not os.path.exists(full_path):
                return {
                    'success': False,
                    'error': f"File not found: {path}"
                }
            
            # Read current content
            with open(full_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Perform replacement
            flags = re.IGNORECASE if ignore_case else 0
            
            if use_regex:
                pattern = re.compile(search, flags)
                if replace_all:
                    new_content = pattern.sub(replace, original_content)
                    count = len(pattern.findall(original_content))
                else:
                    new_content = pattern.sub(replace, original_content, count=1)
                    count = 1 if pattern.search(original_content) else 0
            else:
                if ignore_case:
                    # Case-insensitive literal replacement
                    pattern = re.compile(re.escape(search), flags)
                    if replace_all:
                        new_content = pattern.sub(replace, original_content)
                        count = len(pattern.findall(original_content))
                    else:
                        new_content = pattern.sub(replace, original_content, count=1)
                        count = 1 if pattern.search(original_content) else 0
                else:
                    # Simple string replacement
                    if replace_all:
                        count = original_content.count(search)
                        new_content = original_content.replace(search, replace)
                    else:
                        count = 1 if search in original_content else 0
                        new_content = original_content.replace(search, replace, 1)
            
            if count == 0:
                return {
                    'success': False,
                    'error': f"Search pattern not found: {search[:50]}{'...' if len(search) > 50 else ''}"
                }
            
            # Write new content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Generate simple diff summary
            original_lines = original_content.count('\n')
            new_lines = new_content.count('\n')
            
            logger.info(f"Edited file: {path} ({count} replacement(s))")
            
            return {
                'success': True,
                'path': path,
                'replacements': count,
                'original_lines': original_lines,
                'new_lines': new_lines,
                'timestamp': datetime.now().isoformat()
            }
            
        except re.error as e:
            return {
                'success': False,
                'error': f"Invalid regex pattern: {e}"
            }
        except Exception as e:
            logger.error(f"Error editing file {path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# =============================================================================
# LIST DIRECTORY TOOL
# =============================================================================

class ListDirectoryTool(BaseTool):
    """
    List contents of a directory.
    
    Supports:
    - Recursive listing
    - Filtering by pattern
    - Ignoring common directories (.git, node_modules, etc.)
    - File size and modification time info
    
    Based on Cursor list_dir tool patterns.
    """
    
    MAX_ENTRIES = 200  # Maximum entries to return
    
    def name(self) -> str:
        return "list_directory"
    
    def description(self) -> str:
        return """List files and directories in a path. Directories are marked with a trailing '/'.
Use recursive=true to list all nested contents. Common directories like .git and 
node_modules are automatically ignored."""
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list, relative to project root. Use '.' for project root."
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list contents recursively (default: false)"
                },
                "pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter results (e.g., '*.txt', '*.py')"
                }
            },
            "required": ["project_id", "path"]
        }
    
    def execute(
        self, 
        project_id: str, 
        path: str = ".",
        recursive: bool = False,
        pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List directory contents.
        
        Args:
            project_id: The book project identifier
            path: Path to directory relative to project root
            recursive: Whether to list recursively
            pattern: Optional glob pattern to filter
            
        Returns:
            Dict with directory listing
        """
        try:
            full_path = resolve_path(project_id, path)
            
            if not os.path.exists(full_path):
                return {
                    'success': False,
                    'error': f"Directory not found: {path}"
                }
            
            if not os.path.isdir(full_path):
                return {
                    'success': False,
                    'error': f"Path is not a directory: {path}"
                }
            
            entries = []
            truncated = False
            base_path = get_project_path(project_id)
            
            if recursive:
                for root, dirs, files in os.walk(full_path):
                    # Filter out ignored directories
                    dirs[:] = [d for d in dirs if not should_ignore(d)]
                    
                    for name in dirs:
                        if len(entries) >= self.MAX_ENTRIES:
                            truncated = True
                            break
                        
                        full_item_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_item_path, base_path)
                        
                        if pattern and not fnmatch.fnmatch(name, pattern):
                            continue
                        
                        entries.append({
                            'name': name,
                            'path': rel_path,
                            'type': 'directory'
                        })
                    
                    for name in files:
                        if len(entries) >= self.MAX_ENTRIES:
                            truncated = True
                            break
                        
                        if should_ignore(name):
                            continue
                        
                        full_item_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_item_path, base_path)
                        
                        if pattern and not fnmatch.fnmatch(name, pattern):
                            continue
                        
                        stat = os.stat(full_item_path)
                        entries.append({
                            'name': name,
                            'path': rel_path,
                            'type': 'file',
                            'size': stat.st_size
                        })
                    
                    if truncated:
                        break
            else:
                for name in sorted(os.listdir(full_path)):
                    if len(entries) >= self.MAX_ENTRIES:
                        truncated = True
                        break
                    
                    if should_ignore(name):
                        continue
                    
                    full_item_path = os.path.join(full_path, name)
                    rel_path = os.path.relpath(full_item_path, base_path)
                    
                    if pattern and not fnmatch.fnmatch(name, pattern):
                        continue
                    
                    if os.path.isdir(full_item_path):
                        entries.append({
                            'name': name,
                            'path': rel_path,
                            'type': 'directory'
                        })
                    else:
                        stat = os.stat(full_item_path)
                        entries.append({
                            'name': name,
                            'path': rel_path,
                            'type': 'file',
                            'size': stat.st_size
                        })
            
            # Format output as text tree
            output_lines = []
            for entry in entries:
                if entry['type'] == 'directory':
                    output_lines.append(f"📁 {entry['path']}/")
                else:
                    size_str = self._format_size(entry.get('size', 0))
                    output_lines.append(f"📄 {entry['path']} ({size_str})")
            
            output = '\n'.join(output_lines)
            
            if truncated:
                output += f"\n\n[Truncated: showing {self.MAX_ENTRIES} entries. Use a more specific path.]"
            
            logger.info(f"Listed directory: {path} ({len(entries)} entries)")
            
            return {
                'success': True,
                'path': path,
                'entries': entries,
                'output': output,
                'count': len(entries),
                'truncated': truncated
            }
            
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable form."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != 'B' else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


# =============================================================================
# SEARCH FILES TOOL (by filename)
# =============================================================================

class SearchFilesTool(BaseTool):
    """
    Search for files by name pattern.
    
    Uses glob patterns to find files matching a pattern.
    
    Based on Windsurf fd tool patterns.
    """
    
    MAX_RESULTS = 50
    
    def name(self) -> str:
        return "search_files"
    
    def description(self) -> str:
        return """Search for files by name pattern. Uses glob patterns like '*.txt' or '**/*.py'.
Returns matching file paths. Use '**/' prefix for recursive search."""
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '*.txt', '**/*.py', 'chapter_*.txt')"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in, relative to project root (default: '.')"
                }
            },
            "required": ["project_id", "pattern"]
        }
    
    def execute(
        self, 
        project_id: str, 
        pattern: str,
        path: str = "."
    ) -> Dict[str, Any]:
        """
        Search for files matching a pattern.
        
        Args:
            project_id: The book project identifier
            pattern: Glob pattern to match
            path: Directory to search in
            
        Returns:
            Dict with matching files
        """
        try:
            full_path = resolve_path(project_id, path)
            
            if not os.path.exists(full_path):
                return {
                    'success': False,
                    'error': f"Directory not found: {path}"
                }
            
            # Build search pattern
            search_pattern = os.path.join(full_path, pattern)
            
            # Find matching files
            matches = []
            base_path = get_project_path(project_id)
            
            for match in glob.glob(search_pattern, recursive=True):
                if should_ignore(match):
                    continue
                
                if os.path.isfile(match):
                    rel_path = os.path.relpath(match, base_path)
                    matches.append(rel_path)
                
                if len(matches) >= self.MAX_RESULTS:
                    break
            
            truncated = len(matches) >= self.MAX_RESULTS
            
            output = '\n'.join(matches) if matches else "No files found matching pattern."
            
            if truncated:
                output += f"\n\n[Truncated: showing first {self.MAX_RESULTS} results]"
            
            logger.info(f"File search: {pattern} in {path} ({len(matches)} results)")
            
            return {
                'success': True,
                'pattern': pattern,
                'path': path,
                'matches': matches,
                'output': output,
                'count': len(matches),
                'truncated': truncated
            }
            
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# =============================================================================
# GREP SEARCH TOOL (search file contents)
# =============================================================================

class GrepSearchTool(BaseTool):
    """
    Search for text/pattern within files.
    
    Searches file contents for matching text or regex patterns.
    Returns matches with context.
    
    Based on RooCode search_files and grep_search patterns.
    """
    
    MAX_MATCHES = 100
    CONTEXT_LINES = 2  # Lines of context around each match
    
    def name(self) -> str:
        return "grep_search"
    
    def description(self) -> str:
        return """Search for text or patterns within file contents. Returns matching lines 
with surrounding context. Supports regex patterns and can filter by file type."""
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "query": {
                    "type": "string",
                    "description": "Text or regex pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in, relative to project root (default: '.')"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.txt', '*.py')"
                },
                "use_regex": {
                    "type": "boolean",
                    "description": "Treat query as regex pattern (default: false)"
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case-insensitive search (default: true)"
                }
            },
            "required": ["project_id", "query"]
        }
    
    def execute(
        self, 
        project_id: str, 
        query: str,
        path: str = ".",
        file_pattern: Optional[str] = None,
        use_regex: bool = False,
        ignore_case: bool = True
    ) -> Dict[str, Any]:
        """
        Search for text within files.
        
        Args:
            project_id: The book project identifier
            query: Text or pattern to search for
            path: Directory to search in
            file_pattern: Optional file pattern filter
            use_regex: Treat query as regex
            ignore_case: Case-insensitive search
            
        Returns:
            Dict with search results
        """
        try:
            full_path = resolve_path(project_id, path)
            
            if not os.path.exists(full_path):
                return {
                    'success': False,
                    'error': f"Directory not found: {path}"
                }
            
            # Compile search pattern
            flags = re.IGNORECASE if ignore_case else 0
            if use_regex:
                pattern = re.compile(query, flags)
            else:
                pattern = re.compile(re.escape(query), flags)
            
            matches = []
            base_path = get_project_path(project_id)
            
            # Walk directory
            for root, dirs, files in os.walk(full_path):
                # Filter ignored directories
                dirs[:] = [d for d in dirs if not should_ignore(d)]
                
                for filename in files:
                    if should_ignore(filename):
                        continue
                    
                    # Apply file pattern filter
                    if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, base_path)
                    
                    # Search file
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                            lines = f.readlines()
                        
                        for i, line in enumerate(lines):
                            if pattern.search(line):
                                # Get context
                                start = max(0, i - self.CONTEXT_LINES)
                                end = min(len(lines), i + self.CONTEXT_LINES + 1)
                                
                                context = []
                                for j in range(start, end):
                                    prefix = ">" if j == i else " "
                                    context.append(f"{j+1:4d}{prefix}| {lines[j].rstrip()}")
                                
                                matches.append({
                                    'file': rel_path,
                                    'line': i + 1,
                                    'match': line.strip(),
                                    'context': '\n'.join(context)
                                })
                                
                                if len(matches) >= self.MAX_MATCHES:
                                    break
                    except Exception:
                        # Skip files that can't be read
                        continue
                    
                    if len(matches) >= self.MAX_MATCHES:
                        break
                
                if len(matches) >= self.MAX_MATCHES:
                    break
            
            truncated = len(matches) >= self.MAX_MATCHES
            
            # Format output
            if matches:
                output_parts = []
                for m in matches:
                    output_parts.append(f"📄 {m['file']}:{m['line']}")
                    output_parts.append(m['context'])
                    output_parts.append("")
                output = '\n'.join(output_parts)
            else:
                output = f"No matches found for: {query}"
            
            if truncated:
                output += f"\n[Truncated: showing first {self.MAX_MATCHES} matches]"
            
            logger.info(f"Grep search: '{query}' in {path} ({len(matches)} matches)")
            
            return {
                'success': True,
                'query': query,
                'path': path,
                'matches': matches,
                'output': output,
                'count': len(matches),
                'truncated': truncated
            }
            
        except re.error as e:
            return {
                'success': False,
                'error': f"Invalid regex pattern: {e}"
            }
        except Exception as e:
            logger.error(f"Error in grep search: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# =============================================================================
# DELETE FILE TOOL
# =============================================================================

class DeleteFileTool(BaseTool):
    """
    Delete a file.
    
    Based on Cursor DeleteFile tool.
    """
    
    def name(self) -> str:
        return "delete_file"
    
    def description(self) -> str:
        return "Delete a file from the project. Use with caution - this cannot be undone."
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The book project identifier"
                },
                "path": {
                    "type": "string",
                    "description": "Path to the file to delete, relative to project root"
                }
            },
            "required": ["project_id", "path"]
        }
    
    def execute(self, project_id: str, path: str) -> Dict[str, Any]:
        """
        Delete a file.
        
        Args:
            project_id: The book project identifier
            path: Path to the file relative to project root
            
        Returns:
            Dict with operation result
        """
        try:
            full_path = resolve_path(project_id, path)
            
            if not os.path.exists(full_path):
                return {
                    'success': False,
                    'error': f"File not found: {path}"
                }
            
            if not os.path.isfile(full_path):
                return {
                    'success': False,
                    'error': f"Path is not a file: {path}"
                }
            
            # Get file info before deletion
            stat = os.stat(full_path)
            size = stat.st_size
            
            # Delete the file
            os.remove(full_path)
            
            logger.info(f"Deleted file: {path}")
            
            return {
                'success': True,
                'path': path,
                'deleted_size': size,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

# All available file tools
ALL_FILE_TOOLS = [
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirectoryTool,
    SearchFilesTool,
    GrepSearchTool,
    DeleteFileTool
]


def get_file_tools() -> List[BaseTool]:
    """Get instances of all file tools."""
    return [tool_class() for tool_class in ALL_FILE_TOOLS]
