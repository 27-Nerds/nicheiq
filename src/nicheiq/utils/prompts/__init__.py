"""
Prompt loading utilities for LLM-based components.

Prompts are stored as YAML files for easy editing and maintenance.
"""

from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).parent

def load_prompt(name: str) -> str:
    """
    Load a prompt template from YAML file.

    Args:
        name: Prompt name (without .yaml extension)

    Returns:
        Prompt template string with {placeholders} for formatting

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If YAML doesn't contain 'template' key
    """
    prompt_path = PROMPTS_DIR / f"{name}.yaml"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if "template" not in data:
        raise ValueError(f"Prompt YAML must contain 'template' key: {prompt_path}")

    return data["template"]

def get_prompt(name: str, **kwargs) -> str:
    """
    Load and format a prompt template.

    Args:
        name: Prompt name (without .yaml extension)
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string
    """
    template = load_prompt(name)
    return template.format(**kwargs)
