# Image Prompt Templates

Templates are loaded from this directory at runtime via `backend.prompts.loader.PromptLoader`.
All placeholders use Jinja2 syntax.

## Templates
- `moodboard_sportjacket.md`
- `product_sheet.md`
- `base_rules.md` (shared block injected into other templates)

## Variables
### Moodboard
- `fabric_context_block`
- `fabric_image`
- `occasion`
- `garments_block`
- `jacket_front`
- `shoulder`
- `lapel_style_or_revers`
- `wants_vest_text`
- `trouser_color`
- `shirt`
- `neckwear`
- `material_requirement`
- `design_details`
- `trouser_color_instruction`
- `vest_instruction`
- `constraints_summary_block`
- `style_keywords`
- `scene`
- `base_rules` (content from `base_rules.md`)

### Product Sheet
- `outfit.jacket`, `outfit.trousers`, `outfit.vest`, `outfit.shirt`, `outfit.neckwear`
- `params.occasion`
- `style_keywords`
- `fabric_color`
- `fabric_pattern`
- `fabric_composition`
- `notes_text`
- `base_rules`

## Example
```
from backend.prompts.loader import PromptLoader
loader = PromptLoader()
prompt = loader.render_template(
    "moodboard_sportjacket.md",
    {"fabric_context_block": "- FAB123: navy twill", "scene": "studio"},
)
```
