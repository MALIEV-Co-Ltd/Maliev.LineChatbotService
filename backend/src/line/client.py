"""LINE Messaging API client for sending messages."""

from typing import Any

import aiohttp
import structlog
from aiohttp import ClientTimeout

from ..config.settings import settings
from ..secrets.manager import secret_manager

logger = structlog.get_logger("line.client")


class LineClient:
    """LINE Messaging API client for sending messages and managing LINE bot features."""

    def __init__(self):
        """Initialize LINE client."""
        self._channel_access_token: str | None = None
        self._initialized = False
        self._base_url = "https://api.line.me/v2/bot"
        self._timeout = ClientTimeout(total=30)

    async def initialize(self):
        """Initialize LINE client with credentials."""
        if self._initialized:
            return

        try:
            # Get LINE access token from secret manager
            self._channel_access_token = await secret_manager.get_secret(
                settings.line_channel_access_token or "env:LINE_CHANNEL_ACCESS_TOKEN"
            )

            if not self._channel_access_token:
                logger.warning("LINE channel access token not configured")
            else:
                logger.info("LINE client initialized successfully")

            self._initialized = True

        except Exception as e:
            logger.error("Failed to initialize LINE client", error=str(e))
            raise

    async def send_reply_message(self, reply_token: str, messages: list[dict[str, Any]]) -> bool:
        """Send reply message using LINE reply token."""

        if not self._initialized:
            await self.initialize()

        if not self._channel_access_token:
            logger.warning("Cannot send reply: access token not configured")
            return False

        try:
            url = f"{self._base_url}/message/reply"
            headers = {
                "Authorization": f"Bearer {self._channel_access_token}",
                "Content-Type": "application/json"
            }

            payload = {
                "replyToken": reply_token,
                "messages": messages[:5]  # LINE allows max 5 messages per reply
            }

            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:

                    if response.status == 200:
                        logger.info("Reply message sent successfully",
                                   reply_token=reply_token,
                                   message_count=len(messages))
                        return True
                    else:
                        response_text = await response.text()
                        logger.error("Failed to send reply message",
                                   status=response.status,
                                   response=response_text,
                                   reply_token=reply_token)
                        return False

        except Exception as e:
            logger.error("Error sending reply message",
                        reply_token=reply_token,
                        error=str(e))
            return False

    async def send_push_message(self, user_id: str, messages: list[dict[str, Any]]) -> bool:
        """Send push message to specific user."""

        if not self._initialized:
            await self.initialize()

        if not self._channel_access_token:
            logger.warning("Cannot send push message: access token not configured")
            return False

        try:
            url = f"{self._base_url}/message/push"
            headers = {
                "Authorization": f"Bearer {self._channel_access_token}",
                "Content-Type": "application/json"
            }

            payload = {
                "to": user_id,
                "messages": messages[:5]  # LINE allows max 5 messages per push
            }

            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:

                    if response.status == 200:
                        logger.info("Push message sent successfully",
                                   user_id=user_id,
                                   message_count=len(messages))
                        return True
                    else:
                        response_text = await response.text()
                        logger.error("Failed to send push message",
                                   status=response.status,
                                   response=response_text,
                                   user_id=user_id)
                        return False

        except Exception as e:
            logger.error("Error sending push message",
                        user_id=user_id,
                        error=str(e))
            return False

    async def send_multicast_message(self, user_ids: list[str], messages: list[dict[str, Any]]) -> bool:
        """Send multicast message to multiple users."""

        if not self._initialized:
            await self.initialize()

        if not self._channel_access_token:
            logger.warning("Cannot send multicast message: access token not configured")
            return False

        if len(user_ids) > 500:
            logger.warning("Too many recipients for multicast", count=len(user_ids))
            return False

        try:
            url = f"{self._base_url}/message/multicast"
            headers = {
                "Authorization": f"Bearer {self._channel_access_token}",
                "Content-Type": "application/json"
            }

            payload = {
                "to": user_ids,
                "messages": messages[:5]  # LINE allows max 5 messages per multicast
            }

            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:

                    if response.status == 200:
                        logger.info("Multicast message sent successfully",
                                   user_count=len(user_ids),
                                   message_count=len(messages))
                        return True
                    else:
                        response_text = await response.text()
                        logger.error("Failed to send multicast message",
                                   status=response.status,
                                   response=response_text,
                                   user_count=len(user_ids))
                        return False

        except Exception as e:
            logger.error("Error sending multicast message",
                        user_count=len(user_ids),
                        error=str(e))
            return False

    async def get_profile(self, user_id: str) -> dict[str, Any] | None:
        """Get user profile information."""

        if not self._initialized:
            await self.initialize()

        if not self._channel_access_token:
            logger.warning("Cannot get profile: access token not configured")
            return None

        try:
            url = f"{self._base_url}/profile/{user_id}"
            headers = {
                "Authorization": f"Bearer {self._channel_access_token}"
            }

            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(url, headers=headers) as response:

                    if response.status == 200:
                        profile_data = await response.json()
                        logger.info("Profile retrieved successfully", user_id=user_id)
                        return profile_data
                    else:
                        response_text = await response.text()
                        logger.error("Failed to get profile",
                                   status=response.status,
                                   response=response_text,
                                   user_id=user_id)
                        return None

        except Exception as e:
            logger.error("Error getting profile",
                        user_id=user_id,
                        error=str(e))
            return None

    async def get_group_member_count(self, group_id: str) -> int | None:
        """Get group member count."""

        if not self._initialized:
            await self.initialize()

        if not self._channel_access_token:
            logger.warning("Cannot get group member count: access token not configured")
            return None

        try:
            url = f"{self._base_url}/group/{group_id}/members/count"
            headers = {
                "Authorization": f"Bearer {self._channel_access_token}"
            }

            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(url, headers=headers) as response:

                    if response.status == 200:
                        data = await response.json()
                        count = data.get("count", 0)
                        logger.info("Group member count retrieved", group_id=group_id, count=count)
                        return count
                    else:
                        response_text = await response.text()
                        logger.error("Failed to get group member count",
                                   status=response.status,
                                   response=response_text,
                                   group_id=group_id)
                        return None

        except Exception as e:
            logger.error("Error getting group member count",
                        group_id=group_id,
                        error=str(e))
            return None

    def create_text_message(self, text: str) -> dict[str, Any]:
        """Create LINE text message object."""
        return {
            "type": "text",
            "text": text
        }

    def create_flex_message(self, alt_text: str, contents: dict[str, Any]) -> dict[str, Any]:
        """Create LINE Flex message object."""
        return {
            "type": "flex",
            "altText": alt_text,
            "contents": contents
        }

    def create_template_message(self, alt_text: str, template: dict[str, Any]) -> dict[str, Any]:
        """Create LINE template message object."""
        return {
            "type": "template",
            "altText": alt_text,
            "template": template
        }

    def create_quick_reply(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Create quick reply object."""
        return {
            "items": items[:13]  # LINE allows max 13 quick reply items
        }

    def create_quick_reply_item(self, label: str, text: str, image_url: str | None = None) -> dict[str, Any]:
        """Create quick reply item."""
        item = {
            "type": "action",
            "action": {
                "type": "message",
                "label": label,
                "text": text
            }
        }

        if image_url:
            item["imageUrl"] = image_url

        return item


# Global LINE client instance
line_client = LineClient()
