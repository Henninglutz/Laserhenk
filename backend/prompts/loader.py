from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

PROMPT_ROOT = Path(__file__).parent / "image"


class PromptLoader:
    """Load and render image prompt templates from a fixed directory."""

    def __init__(self, root: Path | None = None):
        self.root = root or PROMPT_ROOT
        self.env = Environment(loader=FileSystemLoader(self.root))

    def load_template(self, name: str) -> str:
        """Load a template file as plain text."""
        path = self.root / name
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")
        return path.read_text(encoding="utf-8")

    def render_template(self, name: str, variables: dict[str, Any]) -> str:
        """Render a template with variables.

        Automatically injects the content of ``base_rules.md`` as ``base_rules``
        when present in the template directory.
        """
        context = dict(variables)
        base_rules_path = self.root / "base_rules.md"
        if "base_rules" not in context and base_rules_path.exists():
            context["base_rules"] = base_rules_path.read_text(encoding="utf-8").strip()

        try:
            template = self.env.get_template(name)
        except TemplateNotFound as exc:  # pragma: no cover - defensive
            raise FileNotFoundError(f"Template not found: {name}") from exc

        rendered = template.render(**context)
        logger.info("[PromptLoader] Rendered template %s", name)
        return rendered.strip()
