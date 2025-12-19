from models.customer import DesignPreferences
from models.patches import DesignPreferencesPatch, PatchDecision, apply_design_preferences_patch


def test_apply_design_preferences_patch_updates_fields():
    existing = DesignPreferences(
        shoulder_padding="medium",
        lapel_style="notch",
        lapel_roll="flat",
        trouser_front="flat_front",
        neckwear="tie",
        notes_normalized="alt",
    )
    patch = DesignPreferencesPatch(
        shoulder_padding="none",
        lapel_style="peak",
        lapel_roll="rolling",
        trouser_front="pleats",
        neckwear="bow_tie",
        notes_normalized="ohne weste, fallendes revers",
    )

    updated = apply_design_preferences_patch(existing, patch)

    assert updated.shoulder_padding == "none"
    assert updated.lapel_style == "peak"
    assert updated.lapel_roll == "rolling"
    assert updated.trouser_front == "pleats"
    assert updated.neckwear == "bow_tie"
    assert updated.notes_normalized == "ohne weste, fallendes revers"


def test_apply_design_preferences_patch_skips_unknown():
    existing = DesignPreferences(
        shoulder_padding="light",
        lapel_style="notch",
        lapel_roll="flat",
    )
    patch = DesignPreferencesPatch(
        shoulder_padding="unknown",
        lapel_style="unknown",
        lapel_roll="unknown",
    )

    updated = apply_design_preferences_patch(existing, patch)

    assert updated.shoulder_padding == "light"
    assert updated.lapel_style == "notch"
    assert updated.lapel_roll == "flat"


def test_patch_decision_schema():
    decision = PatchDecision(
        patch=DesignPreferencesPatch(
            jacket_front="single_breasted",
            button_count=2,
            neckwear="bow_tie",
        ),
        confidence=0.72,
        changed_fields=["jacket_front", "button_count", "neckwear"],
        clarification_questions=[],
    )

    assert decision.confidence == 0.72
    assert decision.patch.button_count == 2
