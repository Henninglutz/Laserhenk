"""Business Models: CRM Deals, Orders, and Payments for HENK System.

Extends CRM functionality and adds order/payment tracking for HITL workflow.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# CRM Deal Models (Bestandskunden)
# ============================================================================


class DealStage(str, Enum):
    """Pipedrive Deal Stages for HENK workflow."""

    INITIAL_CONTACT = "initial_contact"  # Erstkontakt
    CONSULTATION = "consultation"  # Beratungsgespräch
    MEASUREMENT = "measurement"  # Vermessung (SAIA)
    DESIGN_PHASE = "design_phase"  # Design-Ausarbeitung
    FABRIC_SELECTION = "fabric_selection"  # Stoffauswahl
    QUOTE_SENT = "quote_sent"  # Angebot versendet
    QUOTE_ACCEPTED = "quote_accepted"  # Angebot akzeptiert
    PRODUCTION = "production"  # In Produktion
    QUALITY_CHECK = "quality_check"  # Qualitätskontrolle
    DELIVERY = "delivery"  # Auslieferung
    COMPLETED = "completed"  # Abgeschlossen
    LOST = "lost"  # Verloren


class DealPriority(str, Enum):
    """Deal priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class CRMDeal(BaseModel):
    """
    Pipedrive Deal for existing customers.

    Tracks the full lifecycle from consultation to delivery.
    """

    deal_id: str = Field(..., description="Pipedrive Deal ID")
    customer_id: str = Field(..., description="Reference to Customer")
    title: str = Field(..., description="Deal title (e.g., 'Wedding Suit - Max Mustermann')")

    # Deal details
    stage: DealStage = Field(default=DealStage.INITIAL_CONTACT)
    priority: DealPriority = Field(default=DealPriority.MEDIUM)
    value: Optional[float] = Field(None, description="Estimated deal value in EUR", ge=0)
    currency: str = Field(default="EUR")

    # Timeline
    expected_close_date: Optional[datetime] = Field(
        None, description="Expected completion date"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None

    # Status
    is_active: bool = Field(default=True)
    won: Optional[bool] = Field(None, description="True if won, False if lost, None if open")

    # Context
    occasion: Optional[str] = Field(None, description="e.g., 'wedding', 'business'")
    garment_type: Optional[str] = Field(None, description="e.g., 'suit', 'jacket'")
    notes: Optional[str] = Field(None, description="Internal notes")

    # Linked resources
    session_id: Optional[str] = Field(None, description="Link to agent session")
    quote_id: Optional[str] = Field(None, description="Link to quote/order")

    model_config = ConfigDict(use_enum_values=True)


class DealUpdate(BaseModel):
    """Update for CRM Deal (used by agents)."""

    deal_id: str
    stage: Optional[DealStage] = None
    priority: Optional[DealPriority] = None
    value: Optional[float] = None
    expected_close_date: Optional[datetime] = None
    notes: Optional[str] = None
    won: Optional[bool] = None

    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# Order & Quote Models (HITL Workflow)
# ============================================================================


class OrderStatus(str, Enum):
    """Order status lifecycle."""

    DRAFT = "draft"  # In Erstellung (Agent)
    PENDING_REVIEW = "pending_review"  # Wartet auf HITL-Review
    REVIEWED = "reviewed"  # Von HITL geprüft
    QUOTE_SENT = "quote_sent"  # Angebot an Kunden versendet
    CUSTOMER_APPROVED = "customer_approved"  # Kunde hat zugestimmt
    PAYMENT_PENDING = "payment_pending"  # Zahlung ausstehend
    PAYMENT_RECEIVED = "payment_received"  # Zahlung erhalten
    IN_PRODUCTION = "in_production"  # In Produktion
    QUALITY_CHECK = "quality_check"  # Qualitätsprüfung
    READY_FOR_DELIVERY = "ready_for_delivery"  # Versandbereit
    DELIVERED = "delivered"  # Ausgeliefert
    COMPLETED = "completed"  # Abgeschlossen
    CANCELLED = "cancelled"  # Storniert


class OrderItem(BaseModel):
    """Individual item in an order."""

    item_id: str = Field(..., description="Unique item identifier")
    garment_type: str = Field(..., description="e.g., 'jacket', 'trousers', 'vest'")
    fabric_code: str = Field(..., description="Selected fabric")

    # Specifications
    measurements_id: Optional[str] = Field(None, description="Reference to measurements")
    design_preferences: dict = Field(
        default_factory=dict, description="Revers, buttons, pockets, etc."
    )

    # Pricing
    base_price: float = Field(..., description="Base price in EUR", ge=0)
    customization_price: float = Field(
        default=0.0, description="Additional cost for customization", ge=0
    )
    fabric_price: float = Field(..., description="Fabric cost", ge=0)
    total_price: float = Field(..., description="Total item price", ge=0)

    # Metadata
    notes: Optional[str] = None


class OrderQuote(BaseModel):
    """
    Order Quote/Angebot for HITL workflow.

    Created by agents, reviewed by HITL, sent to customer.
    """

    quote_id: str = Field(..., description="Unique quote identifier")
    customer_id: str = Field(..., description="Reference to customer")
    session_id: Optional[str] = Field(None, description="Link to agent session")
    deal_id: Optional[str] = Field(None, description="Link to CRM deal")

    # Items
    items: list[OrderItem] = Field(default_factory=list, description="Order items")

    # Pricing
    subtotal: float = Field(..., description="Sum of all items", ge=0)
    tax_rate: float = Field(default=0.19, description="VAT rate (19% in DE)", ge=0, le=1)
    tax_amount: float = Field(..., description="Tax amount in EUR", ge=0)
    total_amount: float = Field(..., description="Total including tax", ge=0)
    currency: str = Field(default="EUR")

    # Status
    status: OrderStatus = Field(default=OrderStatus.DRAFT)

    # Timeline
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    sent_to_customer_at: Optional[datetime] = None
    customer_approved_at: Optional[datetime] = None
    valid_until: Optional[datetime] = Field(
        None, description="Quote expiration date"
    )

    # HITL Review
    reviewed_by_hitl: bool = Field(default=False)
    hitl_reviewer_id: Optional[str] = None
    hitl_notes: Optional[str] = None
    hitl_approved: Optional[bool] = None

    # Customer communication
    customer_notes: Optional[str] = Field(
        None, description="Notes visible to customer"
    )
    internal_notes: Optional[str] = Field(
        None, description="Internal notes (not visible to customer)"
    )

    # Generated documents
    pdf_url: Optional[str] = Field(None, description="Link to PDF quote")
    visualization_urls: list[str] = Field(
        default_factory=list, description="DALL-E outfit visualizations"
    )

    model_config = ConfigDict(use_enum_values=True)


class OrderQuoteUpdate(BaseModel):
    """Update for order quote (used by HITL)."""

    quote_id: str
    status: Optional[OrderStatus] = None
    hitl_approved: Optional[bool] = None
    hitl_notes: Optional[str] = None
    customer_notes: Optional[str] = None
    valid_until: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# Payment Models (HITL Managed)
# ============================================================================


class PaymentMethod(str, Enum):
    """Payment methods accepted."""

    BANK_TRANSFER = "bank_transfer"  # Überweisung
    CREDIT_CARD = "credit_card"  # Kreditkarte
    PAYPAL = "paypal"
    CASH = "cash"  # Bar
    INVOICE = "invoice"  # Rechnung


class PaymentStatus(str, Enum):
    """Payment status."""

    PENDING = "pending"  # Ausstehend
    PARTIAL = "partial"  # Teilzahlung
    PAID = "paid"  # Bezahlt
    REFUNDED = "refunded"  # Erstattet
    FAILED = "failed"  # Fehlgeschlagen


class PaymentIntent(BaseModel):
    """
    Payment Intent for HITL workflow.

    HITL manages actual payment processing externally.
    This model tracks payment status.
    """

    payment_id: str = Field(..., description="Unique payment identifier")
    quote_id: str = Field(..., description="Reference to order quote")
    customer_id: str = Field(..., description="Reference to customer")

    # Amount
    amount: float = Field(..., description="Payment amount in EUR", ge=0)
    currency: str = Field(default="EUR")

    # Payment details
    payment_method: Optional[PaymentMethod] = None
    payment_status: PaymentStatus = Field(default=PaymentStatus.PENDING)

    # Timeline
    created_at: datetime = Field(default_factory=datetime.now)
    paid_at: Optional[datetime] = None
    due_date: Optional[datetime] = Field(None, description="Payment due date")

    # Partial payments
    amount_paid: float = Field(default=0.0, description="Amount paid so far", ge=0)
    amount_remaining: float = Field(..., description="Remaining amount", ge=0)

    # References
    transaction_reference: Optional[str] = Field(
        None, description="External payment reference (bank, PayPal, etc.)"
    )
    invoice_number: Optional[str] = None

    # Notes
    notes: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# Customer Extensions (for CRM context)
# ============================================================================


class CustomerSegment(str, Enum):
    """Customer segmentation for marketing/CRM."""

    VIP = "vip"  # High-value, repeat customer
    REGULAR = "regular"  # Regular customer
    OCCASIONAL = "occasional"  # Occasional buyer
    NEW = "new"  # First-time customer
    LEAD = "lead"  # Prospect, not yet customer


class CustomerLifetimeValue(BaseModel):
    """Customer Lifetime Value tracking."""

    customer_id: str
    total_revenue: float = Field(default=0.0, description="Total revenue from customer", ge=0)
    total_orders: int = Field(default=0, description="Number of orders", ge=0)
    average_order_value: float = Field(default=0.0, description="Average order value", ge=0)
    segment: CustomerSegment = Field(default=CustomerSegment.NEW)
    last_purchase_date: Optional[datetime] = None
    first_purchase_date: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True)
