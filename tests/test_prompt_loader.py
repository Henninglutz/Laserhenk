import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.prompts.loader import PromptLoader


def test_prompt_loader_renders_variables():
    loader = PromptLoader()
    prompt = loader.render_template(
        "moodboard_sportjacket.md",
        {
            "fabric_context_block": "- FAB123: navy twill",
            "fabric_image": "img.png",
            "occasion": "Business",
            "garments_block": "- Jacket",
            "jacket_front": "single_breasted",
            "shoulder": "light",
            "lapel_style_or_revers": "notch",
            "wants_vest_text": "",
            "trouser_color": "navy",
            "shirt": "white",
            "neckwear": "tie",
            "material_requirement": "fine wool",
            "design_details": "- notch lapels",
            "trouser_color_instruction": "Contrast",
            "vest_instruction": "no vest",
            "constraints_summary_block": "- occasion=Business",
            "style_keywords": "classic",
            "scene": "studio",
        },
    )

    assert "FAB123" in prompt
    assert "Business" in prompt
    assert "classic" in prompt
    assert "Base Image Generation Rules" in prompt
