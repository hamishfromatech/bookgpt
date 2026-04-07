"""
Input validation utilities for BookGPT API.

Provides validation functions for all API inputs to prevent injection attacks
and ensure data integrity.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from functools import wraps


class ValidationError(Exception):
    """Custom exception for validation errors."""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


def validate_string(value: Any, field_name: str, min_length: int = 1, max_length: int = 10000,
                   allow_empty: bool = False, pattern: str = None) -> str:
    """
    Validate a string field.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        min_length: Minimum allowed length
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed
        pattern: Optional regex pattern to match

    Returns:
        The validated and sanitized string

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if not allow_empty:
            raise ValidationError(f"{field_name} is required", field_name)
        return ""

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string", field_name)

    # Strip whitespace
    value = value.strip()

    if not value and not allow_empty:
        raise ValidationError(f"{field_name} cannot be empty", field_name)

    if len(value) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters", field_name)

    if len(value) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters", field_name)

    if pattern and not re.match(pattern, value):
        raise ValidationError(f"{field_name} has invalid format", field_name)

    return value


def validate_integer(value: Any, field_name: str, min_value: int = None, max_value: int = None,
                    required: bool = True) -> int:
    """
    Validate an integer field.

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        required: Whether the field is required

    Returns:
        The validated integer

    Raises:
        ValidationError: If validation fails
    """
    if value is None:
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be an integer", field_name)

    if min_value is not None and value < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value}", field_name)

    if max_value is not None and value > max_value:
        raise ValidationError(f"{field_name} must be at most {max_value}", field_name)

    return value


def validate_email(value: str, field_name: str = "email") -> str:
    """Validate an email address."""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not value:
        raise ValidationError(f"{field_name} is required", field_name)

    value = value.strip().lower()

    if not re.match(email_pattern, value):
        raise ValidationError(f"Invalid {field_name} format", field_name)

    if len(value) > 255:
        raise ValidationError(f"{field_name} is too long", field_name)

    return value


def validate_project_title(value: str) -> str:
    """Validate a project title."""
    return validate_string(value, "title", min_length=1, max_length=200)


def validate_genre(value: str) -> str:
    """Validate a genre."""
    allowed_genres = [
        'fantasy', 'science_fiction', 'scifi', 'mystery', 'thriller',
        'romance', 'horror', 'literary', 'historical', 'nonfiction',
        'memoir', 'biography', 'self_help', 'technical', 'other'
    ]

    value = validate_string(value, "genre", min_length=1, max_length=50)

    # Normalize
    value = value.lower().replace(' ', '_').replace('-', '_')

    if value not in allowed_genres:
        # Allow custom genres but sanitize
        value = re.sub(r'[^a-z0-9_]', '', value)

    return value


def validate_target_length(value: int) -> int:
    """Validate target word length."""
    value = validate_integer(value, "target_length", min_value=1000, max_value=500000)
    return value


def validate_writing_style(value: str) -> str:
    """Validate writing style."""
    from models.version_model import DEFAULT_WRITING_STYLES

    # Get allowed styles
    allowed_styles = list(DEFAULT_WRITING_STYLES.keys())

    value = validate_string(value, "writing_style", min_length=1, max_length=50)

    # Normalize
    value = value.lower().replace(' ', '_')

    # Allow custom styles
    return value


def validate_chapter_number(value: int) -> int:
    """Validate chapter number."""
    return validate_integer(value, "chapter_number", min_value=1, max_value=1000)


def validate_file_path(value: str) -> str:
    """
    Validate a file path to prevent directory traversal attacks.

    Args:
        value: The file path to validate

    Returns:
        Sanitized file path

    Raises:
        ValidationError: If path is invalid or contains dangerous patterns
    """
    if not value:
        raise ValidationError("File path is required", "path")

    # Remove any null bytes
    value = value.replace('\x00', '')

    # Check for directory traversal
    dangerous_patterns = ['../', '..\\', '~/', '/etc/', '/root/', '\\\\']
    for pattern in dangerous_patterns:
        if pattern in value:
            raise ValidationError("Invalid file path", "path")

    # Remove leading slashes and normalize
    value = value.lstrip('/\\')

    # Limit length
    if len(value) > 500:
        raise ValidationError("File path too long", "path")

    return value


def validate_message_content(value: str, max_length: int = 10000) -> str:
    """Validate chat message content."""
    return validate_string(value, "message", min_length=1, max_length=max_length)


def validate_character_name(value: str) -> str:
    """Validate character name."""
    return validate_string(value, "name", min_length=1, max_length=100)


def validate_character_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate character creation/update data."""
    validated = {}

    if 'name' in data:
        validated['name'] = validate_character_name(data['name'])

    if 'description' in data:
        validated['description'] = validate_string(data['description'], "description", max_length=2000, allow_empty=True)

    if 'role' in data:
        validated['role'] = validate_string(data['role'], "role", max_length=50, allow_empty=True)

    if 'backstory' in data:
        validated['backstory'] = validate_string(data['backstory'], "backstory", max_length=5000, allow_empty=True)

    return validated


def validate_plot_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate plot point creation/update data."""
    validated = {}

    if 'title' in data:
        validated['title'] = validate_string(data['title'], "title", min_length=1, max_length=200)

    if 'description' in data:
        validated['description'] = validate_string(data['description'], "description", max_length=5000, allow_empty=True)

    if 'plot_type' in data:
        validated['plot_type'] = validate_string(data['plot_type'], "plot_type", max_length=50)

    if 'importance' in data:
        validated['importance'] = validate_integer(data['importance'], "importance", min_value=1, max_value=5)

    return validated


def sanitize_html(value: str) -> str:
    """
    Remove potentially dangerous HTML tags from a string.

    Args:
        value: String to sanitize

    Returns:
        Sanitized string
    """
    # Remove script tags
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers
    value = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', value, flags=re.IGNORECASE)

    # Remove javascript: URLs
    value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)

    return value


def sanitize_input(value: str) -> str:
    """
    General-purpose input sanitization.

    Args:
        value: String to sanitize

    Returns:
        Sanitized string
    """
    if not value:
        return value

    # Remove null bytes
    value = value.replace('\x00', '')

    # Strip excessive whitespace
    value = value.strip()

    return value


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate a UUID string."""
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'

    if not value:
        raise ValidationError(f"{field_name} is required", field_name)

    value = value.strip().lower()

    if not re.match(uuid_pattern, value):
        raise ValidationError(f"Invalid {field_name} format", field_name)

    return value


def validate_pagination(value: Any, field_name: str, default: int = 1, max_value: int = 100) -> int:
    """Validate pagination parameters."""
    try:
        value = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default

    if value < 1:
        return default

    if value > max_value:
        return max_value

    return value


# Decorator for automatic validation
def validate_request(*validators):
    """
    Decorator to validate request data.

    Usage:
        @validate_request(
            lambda data: validate_project_title(data.get('title')),
            lambda data: validate_genre(data.get('genre'))
        )
        def create_project():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            data = request.get_json() or {}

            errors = []
            for validator in validators:
                try:
                    validator(data)
                except ValidationError as e:
                    errors.append({'field': e.field, 'message': e.message})

            if errors:
                return jsonify({
                    'success': False,
                    'errors': errors,
                    'error': 'Validation failed'
                }), 400

            return f(*args, **kwargs)
        return wrapped
    return decorator