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
    appointment_preferences: Optional[dict] = Field(
        None, description="Structured appointment data (location, date_preference, etc.)"
    )


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
    jacket_front: Optional[str] = Field(
        None, description="single_breasted oder double_breasted"
    )
    button_count: Optional[int] = Field(None, description="Anzahl Knöpfe")
    lapel_style: Optional[str] = Field(
        None, description="notch, peak, shawl, unknown"
    )
    lapel_roll: Optional[str] = Field(
        None, description="rolling, flat, unknown"
    )
    trouser_front: Optional[str] = Field(
        None, description="pleats, flat_front, unknown"
    )
    neckwear: Optional[str] = Field(
        None, description="tie, bow_tie, none, unknown"
    )
    notes_normalized: Optional[str] = Field(
        None, description="Normalized short notes"
    )
    approved_image: Optional[str] = Field(
        None, description="User-approved DALL-E generated outfit image URL"
    )
    preferred_colors: Optional[list[str]] = Field(
        None, description="User's preferred fabric colors for garments (suits, shirts, etc.)"
    )


class FabricSelectionState(BaseModel):
    """Consolidated fabric selection and RAG state."""

    favorite_fabric: Optional[dict] = Field(
        None,
        description="User's selected favorite fabric (fabric_code, name, color, image_url)",
    )
    shown_fabric_images: list[dict] = Field(
        default_factory=list,
        description="History of fabric images shown to user (url, fabric_code, name, timestamp)",
    )
    fabric_presentation_history: list[dict] = Field(
        default_factory=list,
        description="Chronologische Historie kuratierter Stoff-Duos (mid + luxury)",
    )
    rag_context: Optional[dict] = Field(None, description="Context from RAG database")


class ImageGenerationState(BaseModel):
    """Consolidated image generation state."""

    mood_image_url: Optional[str] = Field(
        None, description="Currently displayed DALLE mood image"
    )
    user_uploads: list[str] = Field(
        default_factory=list,
        description="User-uploaded fabric image URLs stored for the session",
    )
    image_generation_history: list[dict] = Field(
        default_factory=list,
        description="History of all generated images (url, type, timestamp, approved)",
    )
    mood_board_iteration_count: int = Field(
        default=0, description="Number of mood board iterations (max 7)"
    )
    mood_board_approved: bool = Field(
        default=False, description="User has approved the mood board"
    )
    mood_board_feedback: Optional[str] = Field(
        None, description="User feedback for mood board iteration"
    )


class AgentProgressState(BaseModel):
    """Consolidated agent progress tracking flags."""

    # RAG query tracking
    henk1_rag_queried: bool = Field(default=False, description="HENK1 has queried RAG")
    henk1_fabrics_shown: bool = Field(
        default=False, description="HENK1 has shown fabric list to user"
    )
    design_rag_queried: bool = Field(
        default=False, description="Design HENK has queried RAG"
    )

    # Image generation tracking
    henk1_mood_board_shown: bool = Field(
        default=False, description="HENK1 has shown mood board"
    )

    # User interaction tracking
    henk1_contact_declined: bool = Field(
        default=False, description="User declined contact request"
    )
    henk1_suit_choice_prompted: bool = Field(
        default=False, description="HENK1 asked about 2/3-piece suit"
    )
    henk1_cut_confirmed: bool = Field(
        default=False, description="Suit cut (2/3-piece + vest) confirmed"
    )

    # Suit configuration
    suit_parts: Optional[str] = Field(
        default=None, description="'2' for 2-piece or '3' for 3-piece"
    )
    wants_vest: Optional[bool] = Field(
        default=None, description="Whether customer wants a vest"
    )


class SessionState(BaseModel):
    """
    Overall session state for LangGraph.

    Refactored to use consolidated sub-states for better organization.
    """

    # Core identifiers
    session_id: str
    customer: Customer

    # Domain models (already well-structured)
    measurements: Optional[Measurements] = None
    design_preferences: DesignPreferences = Field(default_factory=DesignPreferences)

    # Consolidated states (NEW - grouped by domain)
    fabric_state: FabricSelectionState = Field(default_factory=FabricSelectionState)
    image_state: ImageGenerationState = Field(default_factory=ImageGenerationState)
    progress: AgentProgressState = Field(default_factory=AgentProgressState)

    # Conversation and routing
    conversation_history: list[dict] = Field(
        default_factory=list,
        description="Message history as list of dicts with role/content/sender",
    )
    current_agent: Optional[str] = Field(None, description="Current active agent")
    next_action: Optional[str] = None

    # Budget tracking
    customer_budget_status: Optional[str] = Field(
        None, description="Budget status classification (none, range, fixed, unknown)"
    )

    # Handoff payloads (structured agent handoffs)
    handoffs: dict[str, dict] = Field(
        default_factory=dict, description="Structured agent handoffs"
    )
    henk1_to_design_payload: Optional[dict] = Field(
        None, description="HENK1 → Design HENK handoff data"
    )
    design_to_laser_payload: Optional[dict] = Field(
        None, description="Design HENK → LASERHENK handoff data"
    )
    laser_to_hitl_payload: Optional[dict] = Field(
        None, description="LASERHENK → HITL handoff data"
    )

    # BACKWARD COMPATIBILITY: Properties for legacy access patterns
    @property
    def favorite_fabric(self) -> Optional[dict]:
        """Legacy access to fabric_state.favorite_fabric."""
        return self.fabric_state.favorite_fabric

    @favorite_fabric.setter
    def favorite_fabric(self, value: Optional[dict]):
        """Legacy setter for fabric_state.favorite_fabric."""
        self.fabric_state.favorite_fabric = value

    @property
    def shown_fabric_images(self) -> list[dict]:
        """Legacy access to fabric_state.shown_fabric_images."""
        return self.fabric_state.shown_fabric_images

    @property
    def rag_context(self) -> Optional[dict]:
        """Legacy access to fabric_state.rag_context."""
        return self.fabric_state.rag_context

    @rag_context.setter
    def rag_context(self, value: Optional[dict]):
        """Legacy setter for fabric_state.rag_context."""
        self.fabric_state.rag_context = value

    @property
    def mood_image_url(self) -> Optional[str]:
        """Legacy access to image_state.mood_image_url."""
        return self.image_state.mood_image_url

    @mood_image_url.setter
    def mood_image_url(self, value: Optional[str]):
        """Legacy setter for image_state.mood_image_url."""
        self.image_state.mood_image_url = value

    @property
    def image_generation_history(self) -> list[dict]:
        """Legacy access to image_state.image_generation_history."""
        return self.image_state.image_generation_history

    @property
    def henk1_rag_queried(self) -> bool:
        """Legacy access to progress.henk1_rag_queried."""
        return self.progress.henk1_rag_queried

    @henk1_rag_queried.setter
    def henk1_rag_queried(self, value: bool):
        """Legacy setter for progress.henk1_rag_queried."""
        self.progress.henk1_rag_queried = value

    @property
    def henk1_fabrics_shown(self) -> bool:
        """Legacy access to progress.henk1_fabrics_shown."""
        return self.progress.henk1_fabrics_shown

    @henk1_fabrics_shown.setter
    def henk1_fabrics_shown(self, value: bool):
        """Legacy setter for progress.henk1_fabrics_shown."""
        self.progress.henk1_fabrics_shown = value

    @property
    def design_rag_queried(self) -> bool:
        """Legacy access to progress.design_rag_queried."""
        return self.progress.design_rag_queried

    @design_rag_queried.setter
    def design_rag_queried(self, value: bool):
        """Legacy setter for progress.design_rag_queried."""
        self.progress.design_rag_queried = value

    @property
    def henk1_mood_board_shown(self) -> bool:
        """Legacy access to progress.henk1_mood_board_shown."""
        return self.progress.henk1_mood_board_shown

    @henk1_mood_board_shown.setter
    def henk1_mood_board_shown(self, value: bool):
        """Legacy setter for progress.henk1_mood_board_shown."""
        self.progress.henk1_mood_board_shown = value

    @property
    def henk1_contact_declined(self) -> bool:
        """Legacy access to progress.henk1_contact_declined."""
        return self.progress.henk1_contact_declined

    @henk1_contact_declined.setter
    def henk1_contact_declined(self, value: bool):
        """Legacy setter for progress.henk1_contact_declined."""
        self.progress.henk1_contact_declined = value

    @property
    def henk1_suit_choice_prompted(self) -> bool:
        """Legacy access to progress.henk1_suit_choice_prompted."""
        return self.progress.henk1_suit_choice_prompted

    @henk1_suit_choice_prompted.setter
    def henk1_suit_choice_prompted(self, value: bool):
        """Legacy setter for progress.henk1_suit_choice_prompted."""
        self.progress.henk1_suit_choice_prompted = value

    @property
    def suit_parts(self) -> Optional[str]:
        """Legacy access to progress.suit_parts."""
        return self.progress.suit_parts

    @suit_parts.setter
    def suit_parts(self, value: Optional[str]):
        """Legacy setter for progress.suit_parts."""
        self.progress.suit_parts = value

    @property
    def wants_vest(self) -> Optional[bool]:
        """Legacy access to progress.wants_vest."""
        return self.progress.wants_vest

    @wants_vest.setter
    def wants_vest(self, value: Optional[bool]):
        """Legacy setter for progress.wants_vest."""
        self.progress.wants_vest = value

    @property
    def henk1_cut_confirmed(self) -> bool:
        """Legacy access to progress.henk1_cut_confirmed."""
        return self.progress.henk1_cut_confirmed

    @henk1_cut_confirmed.setter
    def henk1_cut_confirmed(self, value: bool):
        """Legacy setter for progress.henk1_cut_confirmed."""
        self.progress.henk1_cut_confirmed = value

    # Lead capture tracking
    henk1_contact_requested: bool = Field(
        default=False, description="HENK1 hat bereits nach Kontaktdaten gefragt"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
