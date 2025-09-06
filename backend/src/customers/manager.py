"""Customer management system with automatic information extraction."""

import json
import re
from datetime import datetime
from typing import Any

import structlog

from ..config.settings import settings
from ..database.redis_client import redis_client

logger = structlog.get_logger("customers")


class CustomerManager:
    """Manages customer profiles, preferences, and interaction history."""

    def __init__(self):
        """Initialize customer manager."""
        self._initialized = False
        self._extraction_patterns = {
            "phone": [
                r"(?:โทร|เบอร์|เบอร์โทร|หมายเลข)[\s:]*([0-9\-\s]{8,15})",
                r"(\d{3}[\-\s]?\d{3}[\-\s]?\d{4})",
                r"(0[689]\d{8})"
            ],
            "email": [
                r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
            ],
            "name": [
                r"ชื่อ[\s:]*([ก-๙a-zA-Z\s]+)",
                r"เรียก[\s:]*([ก-๙a-zA-Z\s]+)",
                r"ผม[\s]?([ก-๙a-zA-Z]+)",
                r"ดิฉัน[\s]?([ก-๙a-zA-Z]+)"
            ]
        }

    async def initialize(self):
        """Initialize customer management system."""
        if self._initialized:
            return

        logger.info("Customer management system initialized")
        self._initialized = True

    async def get_customer(self, user_id: str) -> dict[str, Any] | None:
        """Get customer profile."""

        if not self._initialized:
            await self.initialize()

        try:
            customer_key = f"customer:{user_id}"
            customer_data = await redis_client.hgetall(customer_key)

            if not customer_data:
                return None

            # Parse complex fields
            customer_profile = dict(customer_data)

            # Parse preferences
            if customer_profile.get("preferences"):
                try:
                    customer_profile["preferences"] = json.loads(customer_profile["preferences"])
                except json.JSONDecodeError:
                    customer_profile["preferences"] = {}
            else:
                customer_profile["preferences"] = {}

            # Parse projects
            if customer_profile.get("projects"):
                try:
                    customer_profile["projects"] = json.loads(customer_profile["projects"])
                except json.JSONDecodeError:
                    customer_profile["projects"] = []
            else:
                customer_profile["projects"] = []

            # Parse tags
            if customer_profile.get("tags"):
                customer_profile["tags"] = customer_profile["tags"].split(",")
            else:
                customer_profile["tags"] = []

            # Convert numeric fields
            customer_profile["message_count"] = int(customer_profile.get("message_count", 0))

            return customer_profile

        except Exception as e:
            logger.error("Failed to get customer", user_id=user_id, error=str(e))
            return None

    async def create_customer(self, user_id: str, initial_data: dict[str, Any] | None = None) -> bool:
        """Create new customer profile."""

        try:
            customer_key = f"customer:{user_id}"

            # Check if customer already exists
            exists = await redis_client.exists(customer_key)
            if exists:
                return False

            # Create profile data
            now = datetime.utcnow().isoformat()
            profile_data = {
                "user_id": user_id,
                "name": "",
                "phone": "",
                "email": "",
                "preferences": json.dumps({}),
                "projects": json.dumps([]),
                "tags": "",
                "notes": "",
                "status": "active",
                "source": "line",
                "created_at": now,
                "updated_at": now,
                "last_interaction": now,
                "message_count": "0",
                "total_spent": "0.0",
                "preferred_language": "th"
            }

            # Add initial data if provided
            if initial_data:
                for key, value in initial_data.items():
                    if key in profile_data:
                        if isinstance(value, dict | list):
                            profile_data[key] = json.dumps(value)
                        else:
                            profile_data[key] = str(value)

            # Store customer data
            for field, value in profile_data.items():
                await redis_client.hset(customer_key, field, value)

            logger.info("Customer profile created", user_id=user_id)
            return True

        except Exception as e:
            logger.error("Failed to create customer", user_id=user_id, error=str(e))
            return False

    async def update_customer(self, user_id: str, updates: dict[str, Any]) -> bool:
        """Update customer profile."""

        try:
            customer_key = f"customer:{user_id}"

            # Check if customer exists
            exists = await redis_client.exists(customer_key)
            if not exists:
                return False

            # Prepare updates
            update_data = {}

            for key, value in updates.items():
                if key in ["preferences", "projects"] and isinstance(value, dict | list):
                    update_data[key] = json.dumps(value)
                elif key == "tags" and isinstance(value, list):
                    update_data[key] = ",".join(value)
                else:
                    update_data[key] = str(value)

            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow().isoformat()

            # Apply updates
            for field, value in update_data.items():
                await redis_client.hset(customer_key, field, value)

            logger.info("Customer profile updated", user_id=user_id, fields=list(update_data.keys()))
            return True

        except Exception as e:
            logger.error("Failed to update customer", user_id=user_id, error=str(e))
            return False

    async def process_message_for_extraction(self, user_id: str, message: str) -> dict[str, Any]:
        """Process user message for automatic information extraction."""

        if not settings.auto_extract_customer_info:
            return {"extracted": {}, "changes": []}

        try:
            # Extract information using patterns
            extracted_info = self._extract_info_with_patterns(message)

            # Get current customer profile
            current_profile = await self.get_customer(user_id)

            if not current_profile:
                # Create customer if doesn't exist
                await self.create_customer(user_id)
                current_profile = await self.get_customer(user_id) or {}

            # Determine what to update
            updates = {}
            changes = []

            for field, value in extracted_info.items():
                current_value = current_profile.get(field, "")

                # Only update if field is empty or AI extraction suggests it's better
                if not current_value and value:
                    updates[field] = value
                    changes.append(f"Added {field}: {value}")
                elif current_value != value and await self._should_update_field(current_value, value, field):
                    updates[field] = value
                    changes.append(f"Updated {field}: {current_value} → {value}")

            # Update customer if we have changes
            if updates:
                await self.update_customer(user_id, updates)

            return {
                "extracted": extracted_info,
                "changes": changes,
                "updated": len(updates) > 0
            }

        except Exception as e:
            logger.error("Failed to process message for extraction", user_id=user_id, error=str(e))
            return {"extracted": {}, "changes": []}

    def _extract_info_with_patterns(self, message: str) -> dict[str, Any]:
        """Extract information using regex patterns."""

        extracted = {}

        for field, patterns in self._extraction_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, message, re.IGNORECASE)
                for match in matches:
                    value = match.group(1).strip()

                    # Validate and clean extracted value
                    if field == "phone":
                        cleaned = re.sub(r'[\s\-]', '', value)
                        if len(cleaned) >= 9 and cleaned.isdigit():
                            extracted[field] = cleaned
                    elif field == "email":
                        if "@" in value and "." in value:
                            extracted[field] = value.lower()
                    elif field == "name":
                        if len(value) >= 2 and not value.isdigit():
                            extracted[field] = value

                    # Take first valid match for each field
                    if field in extracted:
                        break

        return extracted

    async def _should_update_field(self, current_value: str, new_value: str, field: str) -> bool:
        """Determine if field should be updated with new value."""

        # For now, keep current values unless they're clearly incomplete
        if field == "phone":
            # Update if new phone number is more complete
            return len(new_value) > len(current_value)
        elif field == "email":
            # Update if new email looks more valid
            return "@" in new_value and "." in new_value
        elif field == "name":
            # Update if new name is longer (more complete)
            return len(new_value) > len(current_value)

        return False

    async def add_project(self, user_id: str, project_data: dict[str, Any]) -> bool:
        """Add project to customer profile."""

        try:
            customer = await self.get_customer(user_id)
            if not customer:
                return False

            # Add project with timestamp
            project_data["created_at"] = datetime.utcnow().isoformat()
            project_data["status"] = project_data.get("status", "inquiry")

            projects = customer.get("projects", [])
            projects.append(project_data)

            # Update customer profile
            return await self.update_customer(user_id, {"projects": projects})

        except Exception as e:
            logger.error("Failed to add project", user_id=user_id, error=str(e))
            return False

    async def add_tag(self, user_id: str, tag: str) -> bool:
        """Add tag to customer profile."""

        try:
            customer = await self.get_customer(user_id)
            if not customer:
                return False

            tags = set(customer.get("tags", []))
            tags.add(tag)

            return await self.update_customer(user_id, {"tags": list(tags)})

        except Exception as e:
            logger.error("Failed to add tag", user_id=user_id, tag=tag, error=str(e))
            return False

    async def update_preferences(self, user_id: str, preferences: dict[str, Any]) -> bool:
        """Update customer preferences."""

        try:
            customer = await self.get_customer(user_id)
            if not customer:
                return False

            current_prefs = customer.get("preferences", {})
            current_prefs.update(preferences)

            return await self.update_customer(user_id, {"preferences": current_prefs})

        except Exception as e:
            logger.error("Failed to update preferences", user_id=user_id, error=str(e))
            return False

    async def increment_message_count(self, user_id: str) -> bool:
        """Increment customer message count."""

        try:
            customer_key = f"customer:{user_id}"

            # Use Redis HINCRBY for atomic increment
            await redis_client.hincrby(customer_key, "message_count", 1)

            # Update last interaction
            await redis_client.hset(customer_key, "last_interaction", datetime.utcnow().isoformat())

            return True

        except Exception as e:
            logger.error("Failed to increment message count", user_id=user_id, error=str(e))
            return False

    async def get_customer_segments(self) -> dict[str, list[str]]:
        """Get customer segmentation."""

        try:
            # Get all customers
            customer_keys = await redis_client.keys("customer:*")

            segments = {
                "new": [],
                "active": [],
                "returning": [],
                "vip": []
            }

            for key in customer_keys:
                customer_data = await redis_client.hgetall(key)
                if not customer_data:
                    continue

                user_id = key.split(":")[-1]
                message_count = int(customer_data.get("message_count", 0))
                created_at = customer_data.get("created_at", "")
                last_interaction = customer_data.get("last_interaction", "")

                # Calculate days since creation
                try:
                    created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    days_since_creation = (datetime.utcnow() - created_date.replace(tzinfo=None)).days
                except:
                    days_since_creation = 0

                # Calculate days since last interaction
                try:
                    last_date = datetime.fromisoformat(last_interaction.replace("Z", "+00:00"))
                    days_since_interaction = (datetime.utcnow() - last_date.replace(tzinfo=None)).days
                except:
                    days_since_interaction = 999

                # Segment customers
                if days_since_creation <= 7:
                    segments["new"].append(user_id)
                elif message_count >= 50 or float(customer_data.get("total_spent", 0)) > 5000:
                    segments["vip"].append(user_id)
                elif days_since_interaction <= 30:
                    segments["active"].append(user_id)
                else:
                    segments["returning"].append(user_id)

            return segments

        except Exception as e:
            logger.error("Failed to get customer segments", error=str(e))
            return {"new": [], "active": [], "returning": [], "vip": []}

    async def search_customers(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search customers by name, phone, email, or tags."""

        try:
            customer_keys = await redis_client.keys("customer:*")
            matching_customers = []

            query_lower = query.lower()

            for key in customer_keys[:limit * 2]:  # Get more than limit to filter
                customer_data = await redis_client.hgetall(key)
                if not customer_data:
                    continue

                # Search in various fields
                searchable_text = " ".join([
                    customer_data.get("name", ""),
                    customer_data.get("phone", ""),
                    customer_data.get("email", ""),
                    customer_data.get("tags", ""),
                    customer_data.get("notes", "")
                ]).lower()

                if query_lower in searchable_text:
                    user_id = key.split(":")[-1]
                    customer_profile = await self.get_customer(user_id)
                    if customer_profile:
                        matching_customers.append(customer_profile)

                if len(matching_customers) >= limit:
                    break

            return matching_customers

        except Exception as e:
            logger.error("Failed to search customers", query=query, error=str(e))
            return []

    async def get_customer_analytics(self, user_id: str) -> dict[str, Any]:
        """Get analytics for specific customer."""

        try:
            customer = await self.get_customer(user_id)
            if not customer:
                return {}

            # Get conversation history length
            conversation_key = f"conversation:{user_id}"
            conversation_length = await redis_client.llen(conversation_key)

            # Calculate engagement metrics
            created_date = datetime.fromisoformat(customer["created_at"].replace("Z", "+00:00"))
            last_interaction = datetime.fromisoformat(customer["last_interaction"].replace("Z", "+00:00"))

            days_active = (datetime.utcnow() - created_date.replace(tzinfo=None)).days + 1
            days_since_last = (datetime.utcnow() - last_interaction.replace(tzinfo=None)).days

            return {
                "basic_info": {
                    "user_id": user_id,
                    "name": customer.get("name", ""),
                    "status": customer.get("status", ""),
                    "source": customer.get("source", "")
                },
                "engagement": {
                    "message_count": customer["message_count"],
                    "conversation_length": conversation_length,
                    "days_active": days_active,
                    "days_since_last_interaction": days_since_last,
                    "avg_messages_per_day": round(customer["message_count"] / max(days_active, 1), 2)
                },
                "projects": {
                    "total_projects": len(customer.get("projects", [])),
                    "active_projects": len([p for p in customer.get("projects", []) if p.get("status") == "active"])
                },
                "profile_completeness": {
                    "has_name": bool(customer.get("name")),
                    "has_phone": bool(customer.get("phone")),
                    "has_email": bool(customer.get("email")),
                    "completion_score": sum([
                        bool(customer.get("name")),
                        bool(customer.get("phone")),
                        bool(customer.get("email"))
                    ]) / 3 * 100
                }
            }

        except Exception as e:
            logger.error("Failed to get customer analytics", user_id=user_id, error=str(e))
            return {}


# Global customer manager instance
customer_manager = CustomerManager()
