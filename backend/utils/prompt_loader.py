"""
Loads agent system prompts from .md files.
Strips YAML frontmatter (--- ... ---) and returns the body as a clean string.
"""
from pathlib import Path
import re

# Root of the repo — two levels up from backend/utils/
_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_DIR = _REPO_ROOT / "claude" / "agents"


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block if present."""
    pattern = re.compile(r"^\s*---\s*\n.*?\n---\s*\n", re.DOTALL)
    return pattern.sub("", text).strip()


def load_agent_prompt(relative_path: str) -> str:
    """
    Load a system prompt from a .md file relative to claude/agents/.

    Examples:
        load_agent_prompt("orchestrator.md")
        load_agent_prompt("subagentes/profiles-orchestrator.md")
    """
    full_path = _AGENTS_DIR / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Agent file not found: {full_path}")
    raw = full_path.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


def load_raw_json(filename: str) -> str:
    """Load a JSON file from the repo root as a raw string (for injecting into prompts)."""
    path = _REPO_ROOT / filename
    return path.read_text(encoding="utf-8")
