"""
Prompt loading utilities for LLM-based components.

Prompts are stored as YAML files for easy editing and maintenance.
"""

from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).parent

# Figures asserted in MORE THAN ONE prompt. A number written as a literal in two templates
# is a number that will eventually disagree with itself: the live 2026-08-03 report told the
# reader to "Conduct 10 structured interviews" in the Brief and "Conduct 5" in the Plan,
# because `report_next_steps.yaml` had no anchor and invented one while the playbook copied
# its own example. Both templates now interpolate from here, so the value cannot drift and
# neither file needs prose claiming the other agrees with it.
#
# Add a constant here whenever a prompt states a figure that another prompt also states.
INTERVIEW_COUNT_RANGE = "5-10"

SHARED_PROMPT_CONSTANTS: dict[str, str] = {
    "interview_count_range": INTERVIEW_COUNT_RANGE,
}

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

def safe_format(template: str, **kwargs) -> str:
    """Format a template, escaping curly braces in string values.

    Prevents KeyError/ValueError when user or LLM content contains
    literal { or } characters (e.g., JSON snippets, code blocks).

    `SHARED_PROMPT_CONSTANTS` are always available to every template and never need to be
    passed by the caller — a cross-prompt figure must not depend on each call site
    remembering it. An explicit kwarg of the same name still wins, so a caller can
    override for a one-off without editing the constant.
    """
    merged = {**SHARED_PROMPT_CONSTANTS, **kwargs}
    escaped = {
        k: v.replace("{", "{{").replace("}", "}}") if isinstance(v, str) else v
        for k, v in merged.items()
    }
    return template.format(**escaped)


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
    return safe_format(template, **kwargs)
