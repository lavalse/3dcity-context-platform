from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache(maxsize=1)
def get_system_prompt() -> str:
    """Load the system prompt from the markdown file."""
    path = _PROMPT_DIR / "system_prompt.md"
    return path.read_text(encoding="utf-8")
