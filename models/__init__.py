"""Models package."""

from models.customer import (
    Customer,
    CustomerType,
    DesignPreferences,
    Measurements,
    SessionState,
)
from models.fabric import (
    FabricColor,
    FabricData,
    FabricPattern,
    FabricRecommendation,
    FabricSearchCriteria,
    Season,
    StockStatus,
)
from models.graph_state import HenkGraphState, create_initial_graph_state
from models.handoff import (
    CustomerCommitment,
    DesignHenkToLaserHenkPayload,
    GarmentType,
    HandoffValidator,
    Henk1ToDesignHenkPayload,
    InnerLiningType,
    JacketForm,
    LaserHenkToHITLPayload,
    OccasionType,
    ReversType,
    ShoulderProcessing,
    StyleType,
)
from models.tools import (
    CRMLeadCreate,
    CRMLeadResponse,
    CRMLeadUpdate,
    DALLEImageRequest,
    DALLEImageResponse,
    RAGQuery,
    RAGResult,
    SAIAMeasurementRequest,
    SAIAMeasurementResponse,
)

__all__ = [
    # Customer models
    "Customer",
    "CustomerType",
    "Measurements",
    "DesignPreferences",
    "SessionState",
    # Graph state
    "HenkGraphState",
    "create_initial_graph_state",
    # Fabric models
    "FabricData",
    "FabricSearchCriteria",
    "FabricRecommendation",
    "Season",
    "FabricPattern",
    "FabricColor",
    "StockStatus",
    # Handoff models
    "Henk1ToDesignHenkPayload",
    "DesignHenkToLaserHenkPayload",
    "LaserHenkToHITLPayload",
    "HandoffValidator",
    # Handoff enums
    "StyleType",
    "OccasionType",
    "GarmentType",
    "JacketForm",
    "ShoulderProcessing",
    "ReversType",
    "InnerLiningType",
    "CustomerCommitment",
    # Tool models
    "RAGQuery",
    "RAGResult",
    "CRMLeadCreate",
    "CRMLeadUpdate",
    "CRMLeadResponse",
    "DALLEImageRequest",
    "DALLEImageResponse",
    "SAIAMeasurementRequest",
    "SAIAMeasurementResponse",
]
