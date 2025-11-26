"""Authentication Models for HENK Frontend Login.

Simple user authentication for frontend access to orders.
Uses argon2 for password hashing.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============================================================================
# User Models
# ============================================================================


class User(BaseModel):
    """
    Simple user account for frontend login.

    Links to Customer for order access.
    """

    user_id: str = Field(..., description="Unique user identifier (UUID)")
    username: str = Field(..., description="Unique username", min_length=3, max_length=50)
    email: EmailStr = Field(..., description="User email (unique)")

    # Password hash stored separately in DB (argon2)
    # Never include password_hash in API responses

    # Profile
    full_name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = None

    # Link to customer data
    customer_id: str = Field(..., description="Link to Customer record")

    # Account status
    is_active: bool = Field(default=True, description="Account active")
    is_verified: bool = Field(default=False, description="Email verified")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None

    model_config = ConfigDict(use_enum_values=True)


class UserCreate(BaseModel):
    """User registration request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Plain password (will be hashed with argon2)")
    full_name: Optional[str] = None
    phone: Optional[str] = None
    customer_id: str = Field(..., description="Link to existing Customer")

    model_config = ConfigDict(use_enum_values=True)


class UserUpdate(BaseModel):
    """User profile update."""

    user_id: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


# ============================================================================
# Authentication Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request."""

    username_or_email: str = Field(..., description="Username or email")
    password: str = Field(..., description="Plain password")


class LoginResponse(BaseModel):
    """Login response with token and user data."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(..., description="Token expiry in seconds")
    user: User = Field(..., description="User profile")


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    user_id: str
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordResetRequest(BaseModel):
    """Password reset request (forgot password)."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation with token."""

    reset_token: str
    new_password: str = Field(..., min_length=8)


# ============================================================================
# Token Models
# ============================================================================


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    sub: str = Field(..., description="Subject (user_id)")
    username: str
    customer_id: str
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")

    model_config = ConfigDict(use_enum_values=True)
