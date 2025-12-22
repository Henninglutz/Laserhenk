"""Models package with lazy imports to avoid optional dependency errors."""

from typing import Any

# Define all exports but don't import them yet
__all__ = [
    # Auth models
    "User",
    "UserCreate",
    "UserUpdate",
    "LoginRequest",
    "LoginResponse",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "TokenPayload",
    # Business models
    "CRMDeal",
    "DealStage",
    "Order",
    "OrderItem",
    "OrderStatus",
    "OrderHistory",
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
    "FabricChunk",
    "OutfitSpec",
    "GeneratedOutfit",
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
    # API payload models
    "ImagePolicyDecision",
    "FabricRef",
    "Citation",
    "ImagePayload",
]


# Lazy import mapping
_LAZY_IMPORTS = {
    # Auth models
    "User": ("models.auth", "User"),
    "UserCreate": ("models.auth", "UserCreate"),
    "UserUpdate": ("models.auth", "UserUpdate"),
    "LoginRequest": ("models.auth", "LoginRequest"),
    "LoginResponse": ("models.auth", "LoginResponse"),
    "PasswordChangeRequest": ("models.auth", "PasswordChangeRequest"),
    "PasswordResetRequest": ("models.auth", "PasswordResetRequest"),
    "PasswordResetConfirm": ("models.auth", "PasswordResetConfirm"),
    "TokenPayload": ("models.auth", "TokenPayload"),
    # Business models
    "CRMDeal": ("models.business", "CRMDeal"),
    "DealStage": ("models.business", "DealStage"),
    "Order": ("models.business", "Order"),
    "OrderItem": ("models.business", "OrderItem"),
    "OrderStatus": ("models.business", "OrderStatus"),
    "OrderHistory": ("models.business", "OrderHistory"),
    # Customer models
    "Customer": ("models.customer", "Customer"),
    "CustomerType": ("models.customer", "CustomerType"),
    "Measurements": ("models.customer", "Measurements"),
    "DesignPreferences": ("models.customer", "DesignPreferences"),
    "SessionState": ("models.customer", "SessionState"),
    # Graph state
    "HenkGraphState": ("models.graph_state", "HenkGraphState"),
    "create_initial_graph_state": ("models.graph_state", "create_initial_graph_state"),
    # Fabric models
    "FabricData": ("models.fabric", "FabricData"),
    "FabricSearchCriteria": ("models.fabric", "FabricSearchCriteria"),
    "FabricRecommendation": ("models.fabric", "FabricRecommendation"),
    "FabricChunk": ("models.fabric", "FabricChunk"),
    "OutfitSpec": ("models.fabric", "OutfitSpec"),
    "GeneratedOutfit": ("models.fabric", "GeneratedOutfit"),
    "Season": ("models.fabric", "Season"),
    "FabricPattern": ("models.fabric", "FabricPattern"),
    "FabricColor": ("models.fabric", "FabricColor"),
    "StockStatus": ("models.fabric", "StockStatus"),
    # Handoff models
    "Henk1ToDesignHenkPayload": ("models.handoff", "Henk1ToDesignHenkPayload"),
    "DesignHenkToLaserHenkPayload": ("models.handoff", "DesignHenkToLaserHenkPayload"),
    "LaserHenkToHITLPayload": ("models.handoff", "LaserHenkToHITLPayload"),
    "HandoffValidator": ("models.handoff", "HandoffValidator"),
    "StyleType": ("models.handoff", "StyleType"),
    "OccasionType": ("models.handoff", "OccasionType"),
    "GarmentType": ("models.handoff", "GarmentType"),
    "JacketForm": ("models.handoff", "JacketForm"),
    "ShoulderProcessing": ("models.handoff", "ShoulderProcessing"),
    "ReversType": ("models.handoff", "ReversType"),
    "InnerLiningType": ("models.handoff", "InnerLiningType"),
    "CustomerCommitment": ("models.handoff", "CustomerCommitment"),
    # Tool models
    "RAGQuery": ("models.tools", "RAGQuery"),
    "RAGResult": ("models.tools", "RAGResult"),
    "CRMLeadCreate": ("models.tools", "CRMLeadCreate"),
    "CRMLeadUpdate": ("models.tools", "CRMLeadUpdate"),
    "CRMLeadResponse": ("models.tools", "CRMLeadResponse"),
    "DALLEImageRequest": ("models.tools", "DALLEImageRequest"),
    "DALLEImageResponse": ("models.tools", "DALLEImageResponse"),
    "SAIAMeasurementRequest": ("models.tools", "SAIAMeasurementRequest"),
    "SAIAMeasurementResponse": ("models.tools", "SAIAMeasurementResponse"),
    # API payload models
    "ImagePolicyDecision": ("models.api_payload", "ImagePolicyDecision"),
    "FabricRef": ("models.api_payload", "FabricRef"),
    "Citation": ("models.api_payload", "Citation"),
    "ImagePayload": ("models.api_payload", "ImagePayload"),
}


def __getattr__(name: str) -> Any:
    """
    Lazy import implementation.

    This allows models to be imported on-demand, avoiding issues with
    optional dependencies (e.g., email-validator for EmailStr in auth models).

    Example:
        from models import User  # Only imports models.auth when User is accessed
    """
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        try:
            import importlib

            module = importlib.import_module(module_name)
            return getattr(module, attr_name)
        except ImportError as e:
            raise ImportError(
                f"Failed to import {name} from {module_name}. "
                f"This might be due to missing optional dependencies. "
                f"Original error: {e}"
            ) from e

    raise AttributeError(f"module 'models' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Return list of available attributes for autocomplete."""
    return __all__
