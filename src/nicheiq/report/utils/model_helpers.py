"""
Model compatibility helpers for report generation.

These utilities handle the dual nature of data in the system:
- Pydantic models (normal runtime)
- Python dicts (when loading from JSON checkpoints)
"""

from typing import Any


def safe_get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """
    Get attribute from Pydantic model or dict (checkpoint compatibility).

    This helper function allows code to work with both:
    - Pydantic BaseModel instances (access via getattr)
    - Python dict objects (access via .get())

    This is necessary because checkpoint data is loaded as raw dicts,
    but runtime data is Pydantic models.

    Args:
        obj: Object to get attribute from (dict or Pydantic model)
        key: Attribute/key name to retrieve
        default: Default value if key doesn't exist

    Returns:
        Attribute value if found, otherwise default

    Examples:
        >>> # Works with Pydantic model
        >>> solution = SolutionIdea(solution_name="Test", ...)
        >>> safe_get_attr(solution, 'solution_name')
        'Test'

        >>> # Works with dict (from checkpoint)
        >>> solution_dict = {"solution_name": "Test", ...}
        >>> safe_get_attr(solution_dict, 'solution_name')
        'Test'

        >>> # Returns default for missing keys
        >>> safe_get_attr({}, 'missing_key', 'default')
        'default'
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
