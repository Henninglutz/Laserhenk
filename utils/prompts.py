"""Simple prompt loader for HENK agents - MVP version."""

import os
from pathlib import Path
from typing import Optional


class PromptLoader:
    """
    Simple file-based prompt loader.

    For MVP: Just reads prompts from a directory.
    No Google Drive API, no complex fallbacks.
    """

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize prompt loader.

        Args:
            prompts_dir: Path to prompts directory (default: from env or ./Promt)
        """
        self.prompts_dir = Path(
            prompts_dir or
            os.getenv("PROMPTS_DIR", "./Promt")
        )

    def load(self, prompt_name: str) -> str:
        """
        Load prompt from file.

        Args:
            prompt_name: Name without extension (e.g., "henk1_prompt")

        Returns:
            Prompt content

        Raises:
            FileNotFoundError: If prompt file not found
        """
        # Try .txt first, then .md
        for ext in [".txt", ".md"]:
            path = self.prompts_dir / f"{prompt_name}{ext}"
            if path.exists():
                return path.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"Prompt not found: {prompt_name} in {self.prompts_dir}"
        )


# Global instance for easy import
_loader = None

def get_loader() -> PromptLoader:
    """Get global prompt loader instance."""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader

def load_prompt(prompt_name: str) -> str:
    """Convenience function to load prompt."""
    return get_loader().load(prompt_name)
