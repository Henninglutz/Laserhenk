"""DALL-E Image Generation Tool.

Generiert Outfit-Visualisierungen und Mood Images für HENK1 und Design Henk Agenten.

AGENT GUIDE:
------------
Dieses Tool wird für folgende Szenarien verwendet:

1. **HENK1 (Bedarfsermittlung)**:
   - Nach erfolgreicher Stoffempfehlung
   - Generiert Outfit-Vorschläge basierend auf Kundenpräferenzen
   - Zeigt visuelle Inspiration für Stilrichtungen

2. **Design Henk (Design Präferenzen)**:
   - Nach Sammlung von Design-Details (Revers, Schulter, Futter)
   - Generiert Mood-Images für finale Outfit-Visualisierung
   - Iterative Anpassung basierend auf Kundenfeedback

3. **LASERHENK (Finalisierung & Verkauf)**:
   - Generiert finale Outfit-Visualisierung mit allen Details
   - Für Verkaufspräsentation

VERWENDUNG:
-----------
```python
# Im Agent Action zurückgeben:
return AgentDecision(
    next_agent="operator",
    action="generate_image",
    action_params={
        "prompt_type": "outfit_visualization",  # oder "mood_board"
        "fabric_data": {...},  # Stoffdaten aus RAG
        "design_preferences": {...},  # Design-Details
        "style_keywords": ["elegant", "modern", "business"]
    },
    message="Erstelle eine Outfit-Visualisierung..."
)
```

PROMPT TYPEN:
-------------
- **outfit_visualization**: Fotorealistische Outfit-Darstellung
- **mood_board**: Stil-Inspiration und Farbkombinationen
- **detail_focus**: Close-up von Details (Revers, Knöpfe, etc.)
- **fabric_texture**: Stoff-Textur Visualisierung

CONDITIONAL EDGES:
------------------
Nach DALL-E Ausführung:
- Bei Erfolg: Rückkehr zum anfragenden Agent mit image_url im State
- Bei Fehler: Rückkehr mit error message, Agent entscheidet über Fallback
- Bei User-Ablehnung: Re-Generation mit angepasstem Prompt

STATE ATTRIBUTES:
-----------------
- `state.mood_image_url`: Gespeicherte Bild-URL
- `state.design_preferences.approved_image`: User-bestätigtes Bild
- `state.dalle_output`: Vollständige DALL-E Response (url, revised_prompt)
- `state.image_generation_history`: Liste aller generierten Bilder pro Session
"""

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from openai import AsyncOpenAI

from models.tools import DALLEImageRequest, DALLEImageResponse

logger = logging.getLogger(__name__)


class DALLETool:
    """
    DALL-E Image Generation Tool.

    Generiert Bilder mit OpenAI DALL-E 3 API.
    Unterstützt Prompt-Templates aus prompts/ Ordner.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DALL-E Tool.

        Args:
            api_key: OpenAI API Key (defaults to OPENAI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")

        self.client = AsyncOpenAI(api_key=self.api_key)
        self.enabled = os.getenv("ENABLE_DALLE", "true").lower() == "true"

        # Prompt templates directory
        self.prompts_dir = Path(__file__).parent.parent / "prompts"

        # Image storage directory
        self.images_dir = Path(__file__).parent.parent / "generated_images"
        self.images_dir.mkdir(exist_ok=True)

        logger.info(f"[DALLETool] Initialized (enabled={self.enabled})")

    def load_prompt_template(self, template_name: str) -> str:
        """
        Lade Prompt-Template aus prompts/ Ordner.

        Args:
            template_name: Name des Templates (z.B. "outfit_visualization")

        Returns:
            Template-Inhalt als String
        """
        template_path = self.prompts_dir / f"{template_name}.txt"

        if not template_path.exists():
            logger.warning(f"[DALLETool] Template nicht gefunden: {template_path}")
            return ""

        with open(template_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def build_prompt(
        self,
        prompt_type: str,
        fabric_data: Optional[Dict[str, Any]] = None,
        design_preferences: Optional[Dict[str, Any]] = None,
        style_keywords: Optional[list[str]] = None,
        custom_additions: Optional[str] = None,
    ) -> str:
        """
        Erstelle DALL-E Prompt aus Template + Daten.

        Args:
            prompt_type: Art des Prompts (outfit_visualization, mood_board, etc.)
            fabric_data: Stoffdaten (Farben, Muster, Textur)
            design_preferences: Design-Details (Revers, Schulter, Futter)
            style_keywords: Stil-Schlagwörter (elegant, modern, etc.)
            custom_additions: Zusätzliche freie Text-Anweisungen

        Returns:
            Vollständiger DALL-E Prompt
        """
        # Lade Template
        template = self.load_prompt_template(prompt_type)

        if not template:
            # Fallback auf generischen Prompt
            logger.warning(f"[DALLETool] Verwende Fallback-Prompt für {prompt_type}")
            template = self.load_prompt_template("default") or ""

        # Baue Prompt-Komponenten
        components = []

        # Base Template
        if template:
            components.append(template)

        # Fabric Data
        if fabric_data:
            fabric_desc = self._format_fabric_description(fabric_data)
            components.append(f"\n\nSTOFF-DETAILS:\n{fabric_desc}")

        # Design Preferences
        if design_preferences:
            design_desc = self._format_design_description(design_preferences)
            components.append(f"\n\nDESIGN-DETAILS:\n{design_desc}")

        # Style Keywords
        if style_keywords:
            keywords_str = ", ".join(style_keywords)
            components.append(f"\n\nSTIL: {keywords_str}")

        # Custom Additions
        if custom_additions:
            components.append(f"\n\n{custom_additions}")

        # Brand Guidelines aus prompts/brand_guidelines.txt
        brand_guidelines = self.load_prompt_template("brand_guidelines")
        if brand_guidelines:
            components.append(f"\n\nBRAND GUIDELINES:\n{brand_guidelines}")

        final_prompt = "\n".join(components)

        logger.info(f"[DALLETool] Prompt erstellt: {len(final_prompt)} Zeichen")
        return final_prompt

    def _format_fabric_description(self, fabric_data: Dict[str, Any]) -> str:
        """Formatiere Stoffdaten für Prompt."""
        parts = []

        if "colors" in fabric_data:
            colors = ", ".join(fabric_data["colors"])
            parts.append(f"Farben: {colors}")

        if "patterns" in fabric_data:
            patterns = ", ".join(fabric_data["patterns"])
            parts.append(f"Muster: {patterns}")

        if "texture" in fabric_data:
            parts.append(f"Textur: {fabric_data['texture']}")

        if "fabric_code" in fabric_data:
            parts.append(f"Stoff-Code: {fabric_data['fabric_code']}")

        return "\n".join(parts)

    def _format_design_description(self, design_prefs: Dict[str, Any]) -> str:
        """Formatiere Design-Präferenzen für Prompt."""
        parts = []

        # Mapping für deutsche Begriffe
        field_names = {
            "revers_type": "Revers-Typ",
            "shoulder_padding": "Schulter-Polsterung",
            "inner_lining": "Futter",
            "jacket_form": "Jackenform",
            "garment_type": "Kleidungstyp",
        }

        for key, label in field_names.items():
            if key in design_prefs and design_prefs[key]:
                value = design_prefs[key]
                parts.append(f"{label}: {value}")

        return "\n".join(parts)

    async def generate_image(
        self,
        request: DALLEImageRequest,
        session_id: Optional[str] = None,
        save_locally: bool = True,
    ) -> DALLEImageResponse:
        """
        Generiere Bild mit DALL-E 3.

        Args:
            request: DALL-E Request mit Prompt
            session_id: Session ID für Datei-Benennung
            save_locally: Bild lokal speichern (zusätzlich zur URL)

        Returns:
            DALL-E Response mit image_url
        """
        if not self.enabled:
            logger.warning("[DALLETool] DALL-E ist deaktiviert (ENABLE_DALLE=false)")
            return DALLEImageResponse(
                image_url="",
                success=False,
                error="DALL-E ist deaktiviert",
            )

        try:
            logger.info(f"[DALLETool] Generiere Bild: {request.prompt[:100]}...")

            # DALL-E 3 API Call
            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=request.prompt,
                size=request.size,
                quality=request.quality,
                style=request.style,
                n=1,  # DALL-E 3 unterstützt nur n=1
            )

            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt

            logger.info(f"[DALLETool] Bild generiert: {image_url}")

            # Optional: Bild lokal speichern
            local_path = None
            if save_locally and image_url:
                local_path = await self._download_and_save_image(
                    image_url, session_id
                )

            return DALLEImageResponse(
                image_url=image_url,
                revised_prompt=revised_prompt,
                success=True,
            )

        except Exception as e:
            logger.error(f"[DALLETool] Fehler bei Bildgenerierung: {e}")
            return DALLEImageResponse(
                image_url="",
                success=False,
                error=str(e),
            )

    async def _download_and_save_image(
        self, image_url: str, session_id: Optional[str] = None
    ) -> str:
        """
        Lade Bild herunter und speichere es lokal.

        Args:
            image_url: DALL-E Image URL
            session_id: Session ID für Datei-Benennung

        Returns:
            Lokaler Dateipfad
        """
        try:
            # Download image
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = response.content

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_prefix = f"{session_id}_" if session_id else ""
            filename = f"{session_prefix}{timestamp}.png"

            filepath = self.images_dir / filename

            # Save to disk
            with open(filepath, "wb") as f:
                f.write(image_data)

            logger.info(f"[DALLETool] Bild gespeichert: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"[DALLETool] Fehler beim Speichern: {e}")
            return ""

    async def generate_outfit_visualization(
        self,
        fabric_data: Dict[str, Any],
        design_preferences: Dict[str, Any],
        style_keywords: Optional[list[str]] = None,
        session_id: Optional[str] = None,
    ) -> DALLEImageResponse:
        """
        High-level Methode: Generiere Outfit-Visualisierung.

        Verwendet vom Design Henk Agent nach Sammlung aller Design-Details.

        Args:
            fabric_data: Stoffdaten aus RAG
            design_preferences: Design-Präferenzen vom User
            style_keywords: Stil-Schlagwörter
            session_id: Session ID

        Returns:
            DALL-E Response mit Outfit-Bild
        """
        prompt = self.build_prompt(
            prompt_type="outfit_visualization",
            fabric_data=fabric_data,
            design_preferences=design_preferences,
            style_keywords=style_keywords,
        )

        request = DALLEImageRequest(
            prompt=prompt,
            style="natural",  # Fotorealistisch
            size="1024x1024",
            quality="hd",  # High quality für finale Präsentation
        )

        return await self.generate_image(request, session_id=session_id)

    async def generate_mood_board(
        self,
        style_keywords: list[str],
        colors: list[str],
        occasion: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> DALLEImageResponse:
        """
        High-level Methode: Generiere Mood Board.

        Verwendet von HENK1 nach Bedarfsermittlung für Stil-Inspiration.

        Args:
            style_keywords: Stil-Schlagwörter (elegant, casual, etc.)
            colors: Farbpalette
            occasion: Anlass (Hochzeit, Business, etc.)
            session_id: Session ID

        Returns:
            DALL-E Response mit Mood Board
        """
        fabric_data = {"colors": colors}
        design_prefs = {}

        custom_additions = ""
        if occasion:
            custom_additions = f"Anlass: {occasion}"

        prompt = self.build_prompt(
            prompt_type="mood_board",
            fabric_data=fabric_data,
            design_preferences=design_prefs,
            style_keywords=style_keywords,
            custom_additions=custom_additions,
        )

        request = DALLEImageRequest(
            prompt=prompt,
            style="vivid",  # Kreativ für Mood Boards
            size="1024x1024",
            quality="standard",
        )

        return await self.generate_image(request, session_id=session_id)


# Singleton instance
_dalle_tool_instance: Optional[DALLETool] = None


def get_dalle_tool() -> DALLETool:
    """Get or create DALLETool singleton instance."""
    global _dalle_tool_instance
    if _dalle_tool_instance is None:
        _dalle_tool_instance = DALLETool()
    return _dalle_tool_instance
