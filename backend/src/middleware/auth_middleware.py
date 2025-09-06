"""Authentication middleware for admin routes."""


import jwt
import structlog
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config.settings import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for handling authentication on admin routes."""

    def __init__(self, app):
        super().__init__(app)
        self.logger = structlog.get_logger("auth")

        # Routes that require authentication
        self.protected_routes = [
            "/api/v1/admin",
            "/api/v1/config",
            "/api/v1/customers",
            "/api/v1/instructions",
            "/api/v1/cache",
            "/api/v1/metrics"
        ]

        # Routes that are always public
        self.public_routes = [
            "/",
            "/health",
            "/webhook",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]

    async def dispatch(self, request: Request, call_next):
        """Process authentication for protected routes."""

        # Skip authentication for public routes
        if any(request.url.path.startswith(route) for route in self.public_routes):
            return await call_next(request)

        # Skip authentication for non-protected routes
        if not any(request.url.path.startswith(route) for route in self.protected_routes):
            return await call_next(request)

        # Check for authentication token
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            self.logger.warning(
                "Missing authorization header",
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Missing authorization header",
                    "path": request.url.path
                }
            )

        # Extract token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authorization scheme")
        except ValueError:
            self.logger.warning(
                "Invalid authorization header format",
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid authorization header format",
                    "path": request.url.path
                }
            )

        # Verify token
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )

            # Add user info to request state
            request.state.user = {
                "username": payload.get("sub"),
                "is_admin": payload.get("is_admin", False),
                "exp": payload.get("exp")
            }

            self.logger.debug(
                "User authenticated",
                username=payload.get("sub"),
                path=request.url.path
            )

        except jwt.ExpiredSignatureError:
            self.logger.warning(
                "Token expired",
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Token expired",
                    "path": request.url.path
                }
            )

        except jwt.InvalidTokenError as e:
            self.logger.warning(
                "Invalid token",
                path=request.url.path,
                method=request.method,
                error=str(e)
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid token",
                    "path": request.url.path
                }
            )

        return await call_next(request)

    def create_access_token(self, username: str, is_admin: bool = False) -> str:
        """Create JWT access token."""
        from datetime import datetime, timedelta

        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        payload = {
            "sub": username,
            "is_admin": is_admin,
            "exp": expire,
            "iat": datetime.utcnow()
        }

        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        self.logger.info(
            "Access token created",
            username=username,
            is_admin=is_admin,
            expires_at=expire.isoformat()
        )

        return token

    def verify_admin_credentials(self, username: str, password: str) -> bool:
        """Verify admin credentials (basic implementation)."""
        # In production, this should check against a secure user store
        return (
            username == settings.admin_username and
            password == settings.admin_password
        )
