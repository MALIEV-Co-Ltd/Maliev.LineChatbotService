"""Authentication endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ...config.settings import settings
from ...middleware.auth_middleware import AuthMiddleware

router = APIRouter()
logger = structlog.get_logger("auth")

# Create auth middleware instance for token operations
auth_middleware = AuthMiddleware(None)


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest) -> LoginResponse:
    """Authenticate user and return JWT token."""

    logger.info("Login attempt", username=credentials.username)

    # Verify credentials
    if not auth_middleware.verify_admin_credentials(credentials.username, credentials.password):
        logger.warning("Invalid login credentials", username=credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = auth_middleware.create_access_token(
        username=credentials.username,
        is_admin=True
    )

    logger.info("User logged in successfully", username=credentials.username)

    return LoginResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user={
            "username": credentials.username,
            "is_admin": True
        }
    )


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Logout endpoint (client-side token invalidation)."""
    logger.info("User logged out")
    return {"message": "Logged out successfully"}


@router.get("/verify")
async def verify_token() -> dict[str, Any]:
    """Verify current token validity."""
    # This endpoint is protected by middleware
    return {
        "valid": True,
        "message": "Token is valid"
    }
