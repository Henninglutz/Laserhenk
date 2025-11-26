"""Authentication and User Management Models for HENK System.

User accounts, authentication, authorization, and session management.
Compatible with PostgreSQL storage.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============================================================================
# User Roles & Permissions
# ============================================================================


class UserRole(str, Enum):
    """User roles with hierarchical permissions."""

    ADMIN = "admin"  # Full system access
    MANAGER = "manager"  # Manage sales, view all data
    SALES = "sales"  # Sales staff, handle customer interactions
    TAILOR = "tailor"  # Production/tailoring staff
    CUSTOMER = "customer"  # End customer with limited access


class PermissionScope(str, Enum):
    """Permission scopes for fine-grained access control."""

    # Customer data
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    CUSTOMERS_DELETE = "customers:delete"

    # Orders
    ORDERS_READ = "orders:read"
    ORDERS_WRITE = "orders:write"
    ORDERS_DELETE = "orders:delete"

    # CRM
    CRM_READ = "crm:read"
    CRM_WRITE = "crm:write"

    # Fabrics
    FABRICS_READ = "fabrics:read"
    FABRICS_WRITE = "fabrics:write"

    # System
    SYSTEM_CONFIG = "system:config"
    SYSTEM_USERS = "system:users"

    # AI Agents
    AGENTS_VIEW = "agents:view"
    AGENTS_MANAGE = "agents:manage"


# Role -> Permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: list(PermissionScope),  # All permissions
    UserRole.MANAGER: [
        PermissionScope.CUSTOMERS_READ,
        PermissionScope.CUSTOMERS_WRITE,
        PermissionScope.ORDERS_READ,
        PermissionScope.ORDERS_WRITE,
        PermissionScope.CRM_READ,
        PermissionScope.CRM_WRITE,
        PermissionScope.FABRICS_READ,
        PermissionScope.AGENTS_VIEW,
    ],
    UserRole.SALES: [
        PermissionScope.CUSTOMERS_READ,
        PermissionScope.CUSTOMERS_WRITE,
        PermissionScope.ORDERS_READ,
        PermissionScope.ORDERS_WRITE,
        PermissionScope.CRM_READ,
        PermissionScope.CRM_WRITE,
        PermissionScope.FABRICS_READ,
    ],
    UserRole.TAILOR: [
        PermissionScope.ORDERS_READ,
        PermissionScope.CUSTOMERS_READ,
        PermissionScope.FABRICS_READ,
    ],
    UserRole.CUSTOMER: [
        PermissionScope.ORDERS_READ,  # Only own orders
        PermissionScope.FABRICS_READ,
    ],
}


# ============================================================================
# User Models
# ============================================================================


class User(BaseModel):
    """
    User account model.

    Stored in PostgreSQL users table.
    """

    user_id: str = Field(..., description="Unique user identifier (UUID)")
    username: str = Field(..., description="Unique username", min_length=3, max_length=50)
    email: EmailStr = Field(..., description="User email (unique)")

    # Authentication (password_hash stored separately in DB)
    # Never include password_hash in API responses
    is_active: bool = Field(default=True, description="Account active status")
    is_verified: bool = Field(default=False, description="Email verified")

    # Role & Permissions
    role: UserRole = Field(default=UserRole.CUSTOMER)
    custom_permissions: list[PermissionScope] = Field(
        default_factory=list, description="Additional custom permissions"
    )

    # Profile
    full_name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

    # Linked customer (for CUSTOMER role)
    customer_id: Optional[str] = Field(
        None, description="Link to Customer record if role=CUSTOMER"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    last_login_ip: Optional[str] = None

    # Account status
    locked_until: Optional[datetime] = Field(
        None, description="Account locked until this time (after failed logins)"
    )
    failed_login_attempts: int = Field(default=0, ge=0)

    model_config = ConfigDict(use_enum_values=True)


class UserCreate(BaseModel):
    """User creation request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Plain password (will be hashed)")
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole = Field(default=UserRole.CUSTOMER)
    customer_id: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class UserUpdate(BaseModel):
    """User update request."""

    user_id: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    custom_permissions: Optional[list[PermissionScope]] = None

    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# Authentication Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request."""

    username_or_email: str = Field(..., description="Username or email")
    password: str = Field(..., description="Plain password")
    remember_me: bool = Field(default=False)


class LoginResponse(BaseModel):
    """Login response with tokens."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(..., description="Access token expiry (seconds)")
    user: User = Field(..., description="User profile")


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="Valid refresh token")


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""

    access_token: str
    token_type: str = Field(default="Bearer")
    expires_in: int


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    user_id: str
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    """Password reset request (forgot password)."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""

    reset_token: str
    new_password: str = Field(..., min_length=8)


# ============================================================================
# Session Models
# ============================================================================


class UserSession(BaseModel):
    """
    User session tracking (stored in PostgreSQL).

    Separate from LangGraph agent sessions.
    """

    session_id: str = Field(..., description="Session identifier (UUID)")
    user_id: str = Field(..., description="Reference to user")

    # Session details
    access_token_jti: str = Field(..., description="JWT ID for access token")
    refresh_token_jti: str = Field(..., description="JWT ID for refresh token")

    # Device/context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_type: Optional[str] = Field(None, description="e.g., 'mobile', 'desktop'")

    # Lifecycle
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(..., description="Session expiration")
    last_activity: datetime = Field(default_factory=datetime.now)

    # Status
    is_active: bool = Field(default=True)
    revoked: bool = Field(default=False, description="Manually revoked")

    model_config = ConfigDict(use_enum_values=True)


class SessionRevoke(BaseModel):
    """Revoke a session."""

    session_id: str
    reason: Optional[str] = Field(None, description="Revocation reason")


# ============================================================================
# API Key Models (for external integrations)
# ============================================================================


class APIKey(BaseModel):
    """
    API Key for external system access.

    Alternative to user login for system-to-system communication.
    """

    key_id: str = Field(..., description="API Key identifier")
    key_hash: str = Field(..., description="Hashed API key (never store plain)")
    user_id: Optional[str] = Field(None, description="Owner user ID")

    # Metadata
    name: str = Field(..., description="Friendly name for the key")
    description: Optional[str] = None

    # Permissions
    scopes: list[PermissionScope] = Field(
        default_factory=list, description="Allowed scopes"
    )

    # Lifecycle
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    last_used: Optional[datetime] = None

    # Status
    is_active: bool = Field(default=True)
    revoked: bool = Field(default=False)

    model_config = ConfigDict(use_enum_values=True)


class APIKeyCreate(BaseModel):
    """Create API key request."""

    name: str = Field(..., description="Friendly name")
    description: Optional[str] = None
    scopes: list[PermissionScope] = Field(default_factory=list)
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True)


class APIKeyResponse(BaseModel):
    """API key creation response (includes plain key ONCE)."""

    key_id: str
    api_key: str = Field(..., description="Plain API key (show only once!)")
    name: str
    scopes: list[PermissionScope]
    expires_at: Optional[datetime]

    model_config = ConfigDict(use_enum_values=True)
