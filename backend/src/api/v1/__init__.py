"""API v1 router configuration."""

from fastapi import APIRouter

from .admin import router as admin_router
from .ai import router as ai_router
from .auth import router as auth_router
from .cache import router as cache_router
from .customers import router as customers_router
from .instructions import router as instructions_router
from .metrics import router as metrics_router

# Main API v1 router
router = APIRouter()

# Include all sub-routers
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(admin_router, prefix="/admin", tags=["Admin"])
router.include_router(ai_router, prefix="/ai", tags=["AI Providers"])
router.include_router(customers_router, prefix="/customers", tags=["Customers"])
router.include_router(instructions_router, prefix="/instructions", tags=["Instructions"])
router.include_router(cache_router, prefix="/cache", tags=["Cache"])
router.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])

__all__ = ["router"]
