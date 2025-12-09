"""Prompt loading utilities with usage tracking."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "Promt"

PROMPT_FILES = {
    "core": "henk_core_prompt_optimized.txt",
    "henk1": "henk1_prompt.txt",
    "henk2": "henk2_prompt_drive_style.txt",
    "henk3": "henk3_prompt_measurement.txt",
}


@dataclass
class PromptMetadata:
    """Metadata about a loaded prompt."""

    name: str
    path: Path
    loaded_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0
    content: Optional[str] = field(default=None, repr=False)

    def mark_used(self) -> None:
        """Update usage counters and timestamps."""
        now = datetime.now(timezone.utc)
        if self.loaded_at is None:
            self.loaded_at = now
        self.last_used_at = now
        self.use_count += 1


class PromptRegistry:
    """Registry for loading and tracking prompt usage."""

    def __init__(self) -> None:
        self._prompts: Dict[str, PromptMetadata] = {}

    def _resolve_path(self, name: str) -> Path:
        """Return the path for a known prompt name."""
        if name not in PROMPT_FILES:
            raise KeyError(f"Unknown prompt name '{name}'")
        return PROMPT_DIR / PROMPT_FILES[name]

    def get_prompt(self, name: str) -> str:
        """Load a prompt and track when it was used.

        Args:
            name: Prompt key defined in PROMPT_FILES.

        Returns:
            The prompt content as string.
        """
        if name not in self._prompts:
            path = self._resolve_path(name)
            content = path.read_text(encoding="utf-8")
            loaded_at = datetime.now(timezone.utc)
            metadata = PromptMetadata(
                name=name, path=path, content=content, loaded_at=loaded_at
            )
            logger.info("[PromptRegistry] Loaded prompt '%s' from %s", name, path)
            self._prompts[name] = metadata
        else:
            metadata = self._prompts[name]
            content = metadata.content or ""

        metadata.mark_used()
        logger.info(
            "[PromptRegistry] Prompt '%s' used (count=%d)", name, metadata.use_count
        )

        return content

    def get_prompt_or_default(self, name: str, fallback_name: str = "core") -> str:
        """Return a prompt, or fall back to another prompt when missing.

        This helper keeps callers simple: they can request an optional prompt and
        automatically fall back to a known-good default without duplicating
        try/except logic. The fallback prompt is loaded and tracked like any other
        prompt.

        Args:
            name: Primary prompt key to load.
            fallback_name: Prompt key to use when ``name`` is unknown. Defaults
                to ``"core"`` as unser zentraler System-Prompt.

        Returns:
            The prompt content for ``name`` or, if unavailable, ``fallback_name``.

        Raises:
            KeyError: If both the primary and fallback prompt names are unknown.
        """

        try:
            return self.get_prompt(name)
        except KeyError:
            # Einfache Fallback-Erklärung: Falls der gewünschte Prompt nicht
            # existiert (z.B. Tippfehler oder noch nicht angelegt), greifen wir
            # automatisch auf einen bekannten Prompt zurück. Standard ist
            # "core", weil er den allgemeinen System-Kontext enthält und in
            # jedem Fall funktioniert.
            logger.warning(
                "[PromptRegistry] Unknown prompt '%s', falling back to '%s'",
                name,
                fallback_name,
            )
            return self.get_prompt(fallback_name)

    def get_usage_report(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Return a serializable snapshot of prompt usage."""
        report: Dict[str, Dict[str, Optional[str]]] = {}
        for name, meta in self._prompts.items():
            report[name] = {
                "path": str(meta.path),
                "loaded_at": meta.loaded_at.isoformat() if meta.loaded_at else None,
                "last_used_at": meta.last_used_at.isoformat()
                if meta.last_used_at
                else None,
                "use_count": meta.use_count,
            }
        return report

    def reset(self) -> None:
        """Clear cached prompts (useful for tests)."""
        self._prompts.clear()


prompt_registry = PromptRegistry()


def load_all_prompts() -> Dict[str, str]:
    """Load and return all known prompts at once.

    Returns:
        Dictionary mapping prompt name to content.
    """
    return {name: prompt_registry.get_prompt(name) for name in PROMPT_FILES}
