from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def get_system_prompt() -> str:
    """Load the system prompt from the markdown file."""
    path = _PROMPT_DIR / "system_prompt.md"
    return path.read_text(encoding="utf-8")
