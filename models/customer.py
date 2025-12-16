"""Customer and Session State Models."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


class CustomerType(str, Enum):
    """Customer type classification."""

    NEW = "new"
    EXISTING = "existing"


class Customer(BaseModel):
    """Customer base information."""

    customer_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    event_date: Optional[str] = None
    event_date_hint: Optional[str] = Field(
        None, description="Soft timing hint (e.g., 'im Sommer', 'in 6 Wochen')"
    )
    customer_type: CustomerType = CustomerType.NEW
    has_measurements: bool = False
    crm_lead_id: Optional[str] = Field(None, description="PIPEDRIVE CRM Lead ID")


class Measurements(BaseModel):
    """Customer measurements from SAIA or manual input."""

    measurement_id: Optional[str] = None
    source: str = Field(..., description="'saia' oder 'manual'")
    shoulder_width: Optional[float] = None
    chest: Optional[float] = None
    waist: Optional[float] = None
    hip: Optional[float] = None
    sleeve_length: Optional[float] = None
    body_length: Optional[float] = None
    inseam: Optional[float] = None
    raw_data: Optional[dict] = Field(None, description="Raw 3D scan data")
    created_at: datetime = Field(default_factory=datetime.now)


class DesignPreferences(BaseModel):
    """Customer design preferences (Revers, Futter, etc.)."""

    revers_type: Optional[str] = Field(None, description="z.B. 'Spitzrevers'")
    revers_width: Optional[float] = Field(None, description="in cm")
    shoulder_padding: Optional[str] = Field(
        None, description="'leicht', 'mittel', 'stark'"
    )
    waistband_type: Optional[str] = Field(None, description="z.B. 'bundfalte', 'ohne'")
    inner_lining: Optional[str] = Field(None, description="Futterstoff-Art")
    lining_color: Optional[str] = None
    button_style: Optional[str] = None
    pocket_style: Optional[str] = None
    additional_notes: Optional[str] = None
    approved_image: Optional[str] = Field(
        None, description="User-approved DALL-E generated outfit image URL"
    )
    preferred_colors: Optional[list[str]] = Field(
        None, description="User's preferred fabric colors for garments (suits, shirts, etc.)"
    )


class SessionState(BaseModel):
    """Overall session state for LangGraph."""

    session_id: str
    customer: Customer
    measurements: Optional[Measurements] = None
    design_preferences: DesignPreferences = Field(default_factory=DesignPreferences)
    conversation_history: list[dict] = Field(default_factory=list, description="Message history as list of dicts with role/content/sender")
    current_agent: Optional[str] = Field(None, description="Current active agent")
    mood_image_url: Optional[str] = Field(
        None, description="Generated DALLE mood image"
    )
    rag_context: Optional[dict] = Field(None, description="Context from RAG database")
    next_action: Optional[str] = None
    customer_budget_status: Optional[str] = Field(
        None, description="Budget status classification (none, range, fixed, unknown)"
    )

    # RAG query tracking per agent
    henk1_rag_queried: bool = Field(default=False, description="HENK1 has queried RAG")
    design_rag_queried: bool = Field(
        default=False, description="Design HENK has queried RAG"
    )

    # DALL-E Image Generation tracking
    henk1_mood_board_shown: bool = Field(
        default=False, description="HENK1 has shown mood board"
    )
    image_generation_history: list[dict] = Field(
        default_factory=list,
        description="History of all generated images (url, type, timestamp, approved)",
    )

    # Fabric Images tracking
    shown_fabric_images: list[dict] = Field(
        default_factory=list,
        description="History of fabric images shown to user (url, fabric_code, name, timestamp)",
    )
    henk1_fabrics_shown: bool = Field(
        default=False, description="Flag ob HENK1 bereits Stoffliste gezeigt hat"
    )
    fabric_presentation_history: list[dict] = Field(
        default_factory=list,
        description="Chronologische Historie kuratierter Stoff-Duos (mid + luxury)",
    )
    favorite_fabric: Optional[dict] = Field(
        None,
        description="User's selected favorite fabric (fabric_code, name, color, image_url)",
    )
    henk1_suit_choice_prompted: bool = Field(
        default=False, description="HENK1 hat bereits nach 2/3-Teiler & Weste gefragt"
    )
    suit_parts: Optional[str] = Field(
        default=None, description="'2' für Zweiteiler oder '3' für Dreiteiler"
    )
    wants_vest: Optional[bool] = Field(
        default=None, description="Ob der Kunde eine Weste möchte"
    )
    henk1_cut_confirmed: bool = Field(
        default=False, description="Schnitt (2/3-Teiler + Weste) ist bestätigt"
    )

    handoffs: dict[str, dict] = Field(
        default_factory=dict, description="Structured agent handoffs"
    )

    # Handoff Payloads (tracking inter-agent data transfer)
    henk1_to_design_payload: Optional[dict] = Field(
        None, description="HENK1 → Design HENK handoff data"
    )
    design_to_laser_payload: Optional[dict] = Field(
        None, description="Design HENK → LASERHENK handoff data"
    )
    laser_to_hitl_payload: Optional[dict] = Field(
        None, description="LASERHENK → HITL handoff data"
    )

    # Lead capture tracking
    henk1_contact_requested: bool = Field(
        default=False, description="HENK1 hat bereits nach Kontaktdaten gefragt"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
