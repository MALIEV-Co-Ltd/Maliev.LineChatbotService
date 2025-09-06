"""Dynamic instruction system endpoints."""

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ...database.redis_client import redis_client

router = APIRouter()
logger = structlog.get_logger("instructions")


class Instruction(BaseModel):
    """Instruction template model."""
    name: str
    content: str
    category: str = "general"
    triggers: list[str] = []
    priority: int = 1
    enabled: bool = True
    variables: dict[str, str] = {}


class InstructionUpdate(BaseModel):
    """Instruction update model."""
    content: str | None = None
    category: str | None = None
    triggers: list[str] | None = None
    priority: int | None = None
    enabled: bool | None = None
    variables: dict[str, str] | None = None


@router.get("/")
async def list_instructions(
    category: str | None = Query(None),
    enabled: bool | None = Query(None)
) -> dict[str, Any]:
    """List all instruction templates."""

    logger.info("Instruction list requested", category=category, enabled=enabled)

    try:
        # Get all instruction keys
        instruction_keys = await redis_client.keys("instruction:*")
        instructions = []

        for key in instruction_keys:
            instruction_data = await redis_client.hgetall(key)
            if instruction_data:
                instruction_name = key.split(":")[-1]

                # Apply filters
                if category and instruction_data.get("category") != category:
                    continue
                if enabled is not None and instruction_data.get("enabled") != str(enabled).lower():
                    continue

                instructions.append({
                    "name": instruction_name,
                    **instruction_data
                })

        return {
            "instructions": instructions,
            "count": len(instructions),
            "filters": {
                "category": category,
                "enabled": enabled
            }
        }

    except Exception as e:
        logger.error("Failed to list instructions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve instructions"
        )


@router.get("/{instruction_name}")
async def get_instruction(instruction_name: str) -> dict[str, Any]:
    """Get specific instruction template."""

    logger.info("Instruction details requested", name=instruction_name)

    try:
        instruction_key = f"instruction:{instruction_name}"
        instruction_data = await redis_client.hgetall(instruction_key)

        if not instruction_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction '{instruction_name}' not found"
            )

        return {
            "name": instruction_name,
            **instruction_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get instruction", error=str(e), name=instruction_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve instruction"
        )


@router.post("/")
async def create_instruction(instruction: Instruction) -> dict[str, Any]:
    """Create new instruction template."""

    logger.info("Instruction creation requested", name=instruction.name)

    try:
        instruction_key = f"instruction:{instruction.name}"

        # Check if instruction already exists
        exists = await redis_client.exists(instruction_key)
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Instruction '{instruction.name}' already exists"
            )

        # Prepare instruction data
        now = datetime.utcnow().isoformat()
        instruction_data = {
            "content": instruction.content,
            "category": instruction.category,
            "triggers": ",".join(instruction.triggers),
            "priority": str(instruction.priority),
            "enabled": str(instruction.enabled).lower(),
            "variables": str(instruction.variables),
            "created_at": now,
            "updated_at": now
        }

        # Store instruction data
        for field, value in instruction_data.items():
            await redis_client.hset(instruction_key, field, value)

        logger.info("Instruction created", name=instruction.name, category=instruction.category)

        return {
            "success": True,
            "message": f"Instruction '{instruction.name}' created successfully",
            "instruction": {
                "name": instruction.name,
                **instruction_data
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create instruction", error=str(e), name=instruction.name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create instruction"
        )


@router.put("/{instruction_name}")
async def update_instruction(instruction_name: str, instruction_update: InstructionUpdate) -> dict[str, Any]:
    """Update instruction template."""

    logger.info("Instruction update requested", name=instruction_name)

    try:
        instruction_key = f"instruction:{instruction_name}"

        # Check if instruction exists
        exists = await redis_client.exists(instruction_key)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction '{instruction_name}' not found"
            )

        # Update only provided fields
        updates = {}
        if instruction_update.content is not None:
            updates["content"] = instruction_update.content
        if instruction_update.category is not None:
            updates["category"] = instruction_update.category
        if instruction_update.triggers is not None:
            updates["triggers"] = ",".join(instruction_update.triggers)
        if instruction_update.priority is not None:
            updates["priority"] = str(instruction_update.priority)
        if instruction_update.enabled is not None:
            updates["enabled"] = str(instruction_update.enabled).lower()
        if instruction_update.variables is not None:
            updates["variables"] = str(instruction_update.variables)

        updates["updated_at"] = datetime.utcnow().isoformat()

        # Apply updates
        for field, value in updates.items():
            await redis_client.hset(instruction_key, field, value)

        logger.info("Instruction updated", name=instruction_name)

        return {
            "success": True,
            "message": f"Instruction '{instruction_name}' updated successfully",
            "updated_fields": list(updates.keys())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update instruction", error=str(e), name=instruction_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update instruction"
        )


@router.delete("/{instruction_name}")
async def delete_instruction(instruction_name: str) -> dict[str, Any]:
    """Delete instruction template."""

    logger.info("Instruction deletion requested", name=instruction_name)

    try:
        instruction_key = f"instruction:{instruction_name}"
        deleted = await redis_client.delete(instruction_key)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instruction '{instruction_name}' not found"
            )

        logger.info("Instruction deleted", name=instruction_name)

        return {
            "success": True,
            "message": f"Instruction '{instruction_name}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete instruction", error=str(e), name=instruction_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete instruction"
        )


@router.post("/generate")
async def generate_dynamic_instructions(context: dict[str, Any]) -> dict[str, Any]:
    """Generate dynamic instructions based on conversation context."""

    logger.info("Dynamic instruction generation requested")

    try:
        # TODO: Implement intelligent instruction selection
        # This would analyze the context and select appropriate instruction templates

        # Placeholder implementation
        selected_instructions = []

        # Get all enabled instructions
        instruction_keys = await redis_client.keys("instruction:*")

        for key in instruction_keys:
            instruction_data = await redis_client.hgetall(key)
            if instruction_data and instruction_data.get("enabled") == "true":
                instruction_name = key.split(":")[-1]

                # Simple matching based on triggers (placeholder)
                triggers = instruction_data.get("triggers", "").split(",")
                if any(trigger.strip().lower() in str(context).lower() for trigger in triggers if trigger.strip()):
                    selected_instructions.append({
                        "name": instruction_name,
                        "content": instruction_data.get("content", ""),
                        "priority": int(instruction_data.get("priority", 1))
                    })

        # Sort by priority
        selected_instructions.sort(key=lambda x: x["priority"], reverse=True)

        # Combine instructions
        combined_content = "\n\n".join([instr["content"] for instr in selected_instructions])

        return {
            "success": True,
            "selected_instructions": [instr["name"] for instr in selected_instructions],
            "combined_content": combined_content,
            "instruction_count": len(selected_instructions)
        }

    except Exception as e:
        logger.error("Failed to generate dynamic instructions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate dynamic instructions"
        )
