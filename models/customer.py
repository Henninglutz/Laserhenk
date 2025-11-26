"""Customer and Session State Models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
    customer_type: CustomerType = CustomerType.NEW
    has_measurements: bool = False
    crm_lead_id: Optional[str] = Field(
        None, description="PIPEDRIVE CRM Lead ID"
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
    waistband_type: Optional[str] = Field(
        None, description="z.B. 'bundfalte', 'ohne'"
    )
    inner_lining: Optional[str] = Field(
        None, description="Futterstoff-Art"
    )
    lining_color: Optional[str] = None
    button_style: Optional[str] = None
    pocket_style: Optional[str] = None
    additional_notes: Optional[str] = None


class SessionState(BaseModel):
    """Overall session state for LangGraph."""

    session_id: str
    customer: Customer
    measurements: Optional[Measurements] = None
    design_preferences: DesignPreferences = Field(
        default_factory=DesignPreferences
    )
    conversation_history: list[str] = Field(default_factory=list)
    current_agent: Optional[str] = Field(
        None, description="Current active agent"
    )
    mood_image_url: Optional[str] = Field(
        None, description="Generated DALLE mood image"
    )
    rag_context: Optional[dict] = Field(
        None, description="Context from RAG database"
    )
    next_action: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
