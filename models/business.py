"""Business Models: Orders and CRM for HENK System.

Simple order tracking and CRM deal management.
No payment processing - handled via HITL.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# CRM Deal Models
# ============================================================================


class DealStage(str, Enum):
    """Deal stages for HENK workflow."""

    INITIAL_CONTACT = "initial_contact"
    CONSULTATION = "consultation"
    MEASUREMENT = "measurement"
    DESIGN_PHASE = "design_phase"
    FABRIC_SELECTION = "fabric_selection"
    QUOTE_SENT = "quote_sent"
    QUOTE_ACCEPTED = "quote_accepted"
    PRODUCTION = "production"
    QUALITY_CHECK = "quality_check"
    DELIVERY = "delivery"
    COMPLETED = "completed"
    LOST = "lost"


class CRMDeal(BaseModel):
    """
    CRM Deal tracking.

    Links customer interaction to orders.
    """

    deal_id: str = Field(..., description="Unique deal identifier")
    customer_id: str = Field(..., description="Reference to Customer")
    title: str = Field(..., description="Deal title")

    # Status
    stage: DealStage = Field(default=DealStage.INITIAL_CONTACT)
    value: Optional[float] = Field(None, description="Estimated value in EUR", ge=0)
    won: Optional[bool] = Field(
        None, description="True if won, False if lost, None if open"
    )

    # Context
    occasion: Optional[str] = Field(None, description="e.g., 'wedding', 'business'")
    garment_type: Optional[str] = Field(None, description="e.g., 'suit', 'jacket'")
    notes: Optional[str] = None

    # Linked resources
    session_id: Optional[str] = Field(None, description="Link to agent session")
    order_id: Optional[str] = Field(None, description="Link to order")

    # Timeline
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expected_close_date: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# Order Models
# ============================================================================


class OrderStatus(str, Enum):
    """Order status lifecycle."""

    DRAFT = "draft"  # In Erstellung (Agent)
    PENDING_REVIEW = "pending_review"  # Wartet auf HITL
    QUOTE_SENT = "quote_sent"  # Angebot versendet
    CUSTOMER_APPROVED = "customer_approved"  # Kunde hat zugestimmt
    IN_PRODUCTION = "in_production"  # In Produktion
    QUALITY_CHECK = "quality_check"
    READY_FOR_DELIVERY = "ready_for_delivery"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderItem(BaseModel):
    """Individual garment in an order."""

    item_id: str = Field(..., description="Unique item identifier")
    garment_type: str = Field(..., description="e.g., 'jacket', 'trousers', 'vest'")
    fabric_code: str = Field(..., description="Selected fabric")

    # Specifications from agent handoffs
    measurements_id: Optional[str] = Field(
        None, description="Reference to measurements"
    )
    design_preferences: dict = Field(
        default_factory=dict, description="Revers, buttons, pockets, etc."
    )

    # Pricing (simple)
    price: float = Field(..., description="Item price in EUR", ge=0)
    notes: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class Order(BaseModel):
    """
    Customer Order.

    Created by agents, reviewed by HITL, tracked for frontend access.
    """

    order_id: str = Field(..., description="Unique order identifier")
    customer_id: str = Field(..., description="Reference to customer")

    # Linked resources
    session_id: Optional[str] = Field(
        None, description="Agent session that created order"
    )
    deal_id: Optional[str] = Field(None, description="CRM deal")

    # Items
    items: list[OrderItem] = Field(default_factory=list, description="Order items")

    # Pricing
    total_amount: float = Field(..., description="Total in EUR", ge=0)
    currency: str = Field(default="EUR")

    # Status
    status: OrderStatus = Field(default=OrderStatus.DRAFT)

    # Timeline
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    sent_to_customer_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    # HITL Review
    reviewed_by_hitl: bool = Field(default=False)
    hitl_notes: Optional[str] = None

    # Customer communication
    customer_notes: Optional[str] = Field(None, description="Notes visible to customer")
    internal_notes: Optional[str] = Field(None, description="Internal notes")

    # Generated assets
    visualization_urls: list[str] = Field(
        default_factory=list, description="DALL-E outfit visualizations"
    )

    model_config = ConfigDict(use_enum_values=True)


class OrderHistory(BaseModel):
    """
    Order history for frontend display.

    Shows current and past orders for a customer.
    """

    customer_id: str
    current_order: Optional[Order] = Field(None, description="Active order")
    past_orders: list[Order] = Field(
        default_factory=list, description="Completed orders"
    )
    total_orders: int = Field(default=0, ge=0)
    total_spent: float = Field(default=0.0, ge=0)

    model_config = ConfigDict(use_enum_values=True)
