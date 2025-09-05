"""Customer management endpoints."""

from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ...database.redis_client import redis_client

router = APIRouter()
logger = structlog.get_logger("customers")


class Customer(BaseModel):
    """Customer model."""
    user_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    preferences: Dict[str, Any] = {}
    projects: List[Dict[str, Any]] = []
    tags: List[str] = []
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_interaction: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Customer update model."""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


@router.get("/")
async def list_customers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None
) -> Dict[str, Any]:
    """List customers with pagination and search."""
    
    logger.info("Customer list requested", limit=limit, offset=offset, search=search)
    
    try:
        # Get all customer keys
        customer_keys = await redis_client.keys("customer:*")
        
        customers = []
        total = len(customer_keys)
        
        # Apply search filter if provided
        if search:
            filtered_keys = []
            for key in customer_keys:
                customer_data = await redis_client.hgetall(key)
                if (search.lower() in customer_data.get("name", "").lower() or
                    search.lower() in customer_data.get("phone", "").lower() or
                    search.lower() in customer_data.get("email", "").lower()):
                    filtered_keys.append(key)
            customer_keys = filtered_keys
            total = len(customer_keys)
        
        # Apply pagination
        paginated_keys = customer_keys[offset:offset + limit]
        
        for key in paginated_keys:
            customer_data = await redis_client.hgetall(key)
            if customer_data:
                user_id = key.split(":")[-1]
                customers.append({
                    "user_id": user_id,
                    **customer_data
                })
        
        return {
            "customers": customers,
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(customers)
        }
        
    except Exception as e:
        logger.error("Failed to list customers", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve customers"
        )


@router.get("/{user_id}")
async def get_customer(user_id: str) -> Dict[str, Any]:
    """Get customer by user ID."""
    
    logger.info("Customer details requested", user_id=user_id)
    
    try:
        customer_key = f"customer:{user_id}"
        customer_data = await redis_client.hgetall(customer_key)
        
        if not customer_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer '{user_id}' not found"
            )
        
        return {
            "user_id": user_id,
            **customer_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get customer", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve customer"
        )


@router.post("/")
async def create_customer(customer: Customer) -> Dict[str, Any]:
    """Create new customer."""
    
    logger.info("Customer creation requested", user_id=customer.user_id)
    
    try:
        customer_key = f"customer:{customer.user_id}"
        
        # Check if customer already exists
        exists = await redis_client.exists(customer_key)
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer '{customer.user_id}' already exists"
            )
        
        # Prepare customer data
        now = datetime.utcnow().isoformat()
        customer_data = {
            "name": customer.name or "",
            "phone": customer.phone or "",
            "email": customer.email or "",
            "preferences": str(customer.preferences),
            "projects": str(customer.projects),
            "tags": ",".join(customer.tags),
            "notes": customer.notes,
            "created_at": now,
            "updated_at": now,
            "last_interaction": now
        }
        
        # Store customer data
        for field, value in customer_data.items():
            await redis_client.hset(customer_key, field, value)
        
        logger.info("Customer created", user_id=customer.user_id)
        
        return {
            "success": True,
            "message": f"Customer '{customer.user_id}' created successfully",
            "customer": {
                "user_id": customer.user_id,
                **customer_data
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create customer", error=str(e), user_id=customer.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create customer"
        )


@router.put("/{user_id}")
async def update_customer(user_id: str, customer_update: CustomerUpdate) -> Dict[str, Any]:
    """Update customer information."""
    
    logger.info("Customer update requested", user_id=user_id)
    
    try:
        customer_key = f"customer:{user_id}"
        
        # Check if customer exists
        exists = await redis_client.exists(customer_key)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer '{user_id}' not found"
            )
        
        # Update only provided fields
        updates = {}
        if customer_update.name is not None:
            updates["name"] = customer_update.name
        if customer_update.phone is not None:
            updates["phone"] = customer_update.phone
        if customer_update.email is not None:
            updates["email"] = customer_update.email
        if customer_update.preferences is not None:
            updates["preferences"] = str(customer_update.preferences)
        if customer_update.tags is not None:
            updates["tags"] = ",".join(customer_update.tags)
        if customer_update.notes is not None:
            updates["notes"] = customer_update.notes
        
        updates["updated_at"] = datetime.utcnow().isoformat()
        
        # Apply updates
        for field, value in updates.items():
            await redis_client.hset(customer_key, field, value)
        
        logger.info("Customer updated", user_id=user_id)
        
        return {
            "success": True,
            "message": f"Customer '{user_id}' updated successfully",
            "updated_fields": list(updates.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update customer", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update customer"
        )


@router.delete("/{user_id}")
async def delete_customer(user_id: str) -> Dict[str, Any]:
    """Delete customer and all associated data."""
    
    logger.info("Customer deletion requested", user_id=user_id)
    
    try:
        customer_key = f"customer:{user_id}"
        
        # Delete customer data
        deleted = await redis_client.delete(customer_key)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer '{user_id}' not found"
            )
        
        # TODO: Delete associated conversation history, cache entries, etc.
        conversation_keys = await redis_client.keys(f"conversation:{user_id}:*")
        if conversation_keys:
            await redis_client.delete(*conversation_keys)
        
        logger.info("Customer deleted", user_id=user_id)
        
        return {
            "success": True,
            "message": f"Customer '{user_id}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete customer", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete customer"
        )