"""Handoff Payload Models for Agent-to-Agent communication."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.fabric import FabricColor, FabricPattern, Season


# ============================================================================
# HENK1 → Design HENK Mandatory Fields
# ============================================================================


class StyleType(str, Enum):
    """Clothing style types."""

    BUSINESS = "business"
    CASUAL = "casual"
    FORMAL = "formal"
    SMART_CASUAL = "smart_casual"
    CREATIVE = "creative"


class OccasionType(str, Enum):
    """Occasion types."""

    BUSINESS_MEETING = "business_meeting"
    WEDDING = "wedding"
    GALA = "gala"
    EVERYDAY = "everyday"
    PARTY = "party"
    OTHER = "other"


class Henk1ToDesignHenkPayload(BaseModel):
    """
    Mandatory data from HENK1 to Design HENK.

    HENK1 ermittelt diese Daten während der Bedarfsermittlung (AIDA).
    """

    # Mandatory Fields
    budget_min: float = Field(..., description="Minimum Budget in EUR", gt=0)
    budget_max: float = Field(..., description="Maximum Budget in EUR", gt=0)
    style: StyleType = Field(..., description="Gewünschter Stil")
    occasion: OccasionType = Field(..., description="Anlass")

    # Fabric preferences (type-safe with enums)
    patterns: list[FabricPattern] = Field(
        ...,
        min_length=1,
        description="Liste von Mustern (z.B. ['fischgrat', 'uni', 'karo'])",
    )
    colors: list[FabricColor] = Field(
        ...,
        min_length=1,
        description="Liste von Farben (z.B. ['navy', 'grau', 'schwarz'])",
    )
    season: Optional[Season] = Field(
        None, description="Gewünschte Saison (wedding, summer, 4season, winter)"
    )

    # Optional Context
    customer_notes: Optional[str] = Field(
        None, description="Zusätzliche Notizen aus Bedarfsermittlung"
    )
    setting: Optional[str] = Field(
        None, description="Setting/Kontext (z.B. 'see', 'kirche', 'standesamt')"
    )
    fabric_references: list[str] = Field(
        default_factory=list,
        description="Kuratiertes Duo an Stoff-Referenzen (mid + luxury)",
        max_length=2,
    )
    preferred_fabric_tier: Optional[str] = Field(
        None,
        description="Favorisierte Preisstufe des Nutzers (mid oder luxury)",
        pattern="^(mid|luxury)$",
    )

    @field_validator("budget_max")
    @classmethod
    def validate_budget_range(cls, v, info):
        """Validate that budget_max >= budget_min."""
        if "budget_min" in info.data and v < info.data["budget_min"]:
            raise ValueError("budget_max must be >= budget_min")
        return v


# ============================================================================
# Design HENK → LASERHENK Mandatory Fields
# ============================================================================


class GarmentType(str, Enum):
    """Garment type: Anzug or Kombination."""

    ANZUG = "anzug"
    KOMBINATION = "kombination"


class JacketForm(str, Enum):
    """Jacket form types."""

    SLIM_FIT = "slim_fit"
    REGULAR_FIT = "regular_fit"
    COMFORT_FIT = "comfort_fit"
    CLASSIC_FIT = "classic_fit"


class ShoulderProcessing(str, Enum):
    """Shoulder processing types."""

    SOFT = "soft"  # Weiche Schulter
    MEDIUM = "medium"  # Mittlere Polsterung
    STRONG = "strong"  # Starke Polsterung
    NATURAL = "natural"  # Natürliche Schulter


class ReversType(str, Enum):
    """Lapel (Revers) types."""

    SPITZREVERS = "spitzrevers"  # Notch lapel
    STEIGENDES_REVERS = "steigendes_revers"  # Peak lapel
    SCHALKRAGEN = "schalkragen"  # Shawl collar


class InnerLiningType(str, Enum):
    """Inner lining types."""

    FULL_LINING = "full_lining"  # Komplett gefüttert
    HALF_LINING = "half_lining"  # Halb gefüttert
    QUARTER_LINING = "quarter_lining"  # Viertel gefüttert
    BEMBERG = "bemberg"  # Bemberg-Futter
    SILK = "silk"  # Seidenfutter


class DesignHenkToLaserHenkPayload(BaseModel):
    """
    Mandatory data from Design HENK to LASERHENK.

    Design HENK sammelt diese Daten während der Designabfrage.
    """

    # Mandatory Fields
    garment_type: GarmentType = Field(..., description="Anzug oder Kombination")
    jacket_form: JacketForm = Field(..., description="Jacket Form")
    shoulder_processing: ShoulderProcessing = Field(
        ..., description="Schulter Verarbeitung"
    )
    revers_type: ReversType = Field(..., description="Revers-Typ")
    inner_lining: InnerLiningType = Field(..., description="Innenfutter")

    # Optional but important
    revers_width_cm: Optional[float] = Field(
        None, description="Reversbreite in cm", gt=0
    )
    lining_color: Optional[str] = Field(None, description="Farbe des Innenfutters")
    button_style: Optional[str] = None
    pocket_style: Optional[str] = None

    # Design context
    mood_image_url: Optional[str] = Field(
        None, description="DALLE generiertes Moodbild"
    )


# ============================================================================
# LASERHENK → HITL Termin Mandatory Fields
# ============================================================================


class CustomerCommitment(str, Enum):
    """Customer commitment level."""

    COMMITTED = "committed"  # Kunde hat zugestimmt
    PENDING = "pending"  # Wartet auf Bestätigung
    CANCELLED = "cancelled"  # Abgesagt


class LaserHenkToHITLPayload(BaseModel):
    """
    Mandatory data from LASERHENK to HITL Termin.

    LASERHENK bereitet Termin vor mit allen finalen Daten.
    """

    # Mandatory Fields
    customer_commitment: CustomerCommitment = Field(
        ..., description="Commitment-Status vom User"
    )
    mood_image_url: str = Field(..., description="Finales Moodbild")
    process_description: str = Field(..., description="Ablaufbeschreibung für Kunden")
    invoice_sent: bool = Field(default=False, description="Rechnung versendet")
    crm_lead_id: str = Field(..., description="CRM Lead ID (Leadsicherung)")

    # Appointment details
    appointment_date: Optional[str] = Field(
        None, description="Terminvereinbarung (ISO format)"
    )
    appointment_location: Optional[str] = Field(
        None, description="Termin-Ort (beim Kunden oder im Studio)"
    )

    # Final summary
    design_summary: dict = Field(
        ..., description="Zusammenfassung aller Design-Entscheidungen"
    )
    measurement_summary: Optional[dict] = Field(
        None, description="Maße (falls bereits vorhanden)"
    )


# ============================================================================
# Handoff Validation Helper
# ============================================================================


class HandoffValidator:
    """Helper class to validate handoffs between agents."""

    @staticmethod
    def validate_henk1_to_design(
        payload: Henk1ToDesignHenkPayload,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate HENK1 → Design HENK handoff.

        Returns:
            (is_valid, error_message)
        """
        try:
            # Pydantic validates automatically
            payload.model_validate(payload.model_dump())
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def validate_design_to_laser(
        payload: DesignHenkToLaserHenkPayload,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate Design HENK → LASERHENK handoff.

        Returns:
            (is_valid, error_message)
        """
        try:
            payload.model_validate(payload.model_dump())
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def validate_laser_to_hitl(
        payload: LaserHenkToHITLPayload,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate LASERHENK → HITL handoff.

        Returns:
            (is_valid, error_message)
        """
        try:
            payload.model_validate(payload.model_dump())

            # Additional business logic validation
            if (
                payload.customer_commitment == CustomerCommitment.COMMITTED
                and not payload.crm_lead_id
            ):
                return False, "CRM Lead ID required for committed customers"

            return True, None
        except Exception as e:
            return False, str(e)
