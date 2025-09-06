"""LINE webhook handler with signature verification."""

import hashlib
import hmac
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog
from fastapi import Request, HTTPException, status

from ..config.settings import settings
from ..database.redis_client import redis_client
from ..secrets.manager import secret_manager
from ..ai import ai_manager, AIMessage
from .models import LineEvent, MessageEvent, FollowEvent, UnfollowEvent
from .client import line_client

logger = structlog.get_logger("line.webhook")


class LineWebhookHandler:
    """Handles LINE webhook events with signature verification."""
    
    def __init__(self):
        """Initialize LINE webhook handler."""
        self._channel_secret: Optional[str] = None
        self._channel_access_token: Optional[str] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize LINE credentials."""
        if self._initialized:
            return
        
        try:
            # Get LINE credentials from secret manager
            self._channel_secret = await secret_manager.get_secret(
                settings.line_channel_secret or "env:LINE_CHANNEL_SECRET"
            )
            self._channel_access_token = await secret_manager.get_secret(
                settings.line_channel_access_token or "env:LINE_CHANNEL_ACCESS_TOKEN"
            )
            
            if not self._channel_secret:
                logger.warning("LINE channel secret not configured")
            if not self._channel_access_token:
                logger.warning("LINE channel access token not configured")
            
            logger.info("LINE webhook handler initialized")
            self._initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize LINE webhook handler", error=str(e))
            raise
    
    async def handle_webhook(self, request: Request) -> Dict[str, Any]:
        """Handle incoming LINE webhook request."""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get request body
            body = await request.body()
            
            # Verify signature
            signature = request.headers.get("x-line-signature")
            if not signature:
                logger.warning("Missing LINE signature header")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing signature header"
                )
            
            if not self._verify_signature(body, signature):
                logger.warning("Invalid LINE signature")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid signature"
                )
            
            # Parse webhook data
            webhook_data = json.loads(body.decode('utf-8'))
            
            logger.info("LINE webhook received", 
                       destination=webhook_data.get("destination"),
                       events_count=len(webhook_data.get("events", [])))
            
            # Process events
            results = []
            for event_data in webhook_data.get("events", []):
                try:
                    result = await self._process_event(event_data)
                    results.append(result)
                except Exception as e:
                    logger.error("Failed to process LINE event", event=event_data, error=str(e))
                    results.append({"success": False, "error": str(e)})
            
            return {
                "success": True,
                "processed_events": len(results),
                "results": results
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("LINE webhook processing failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing failed"
            )
    
    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify LINE webhook signature."""
        
        if not self._channel_secret:
            logger.warning("Cannot verify signature: channel secret not configured")
            # For development testing, allow bypass when secret is not configured
            from ..config.settings import settings
            if settings.environment == "development":
                logger.info("Development mode: bypassing signature verification")
                return True
            return False
        
        try:
            # Generate expected signature
            hash_digest = hmac.new(
                self._channel_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()
            
            expected_signature = hash_digest.hex()
            
            # Compare signatures (remove 'sha256=' prefix if present)
            provided_signature = signature.replace("sha256=", "")
            
            return hmac.compare_digest(expected_signature, provided_signature)
            
        except Exception as e:
            logger.error("Signature verification failed", error=str(e))
            return False
    
    async def _process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process individual LINE event."""
        
        event_type = event_data.get("type")
        user_id = event_data.get("source", {}).get("userId")
        timestamp = event_data.get("timestamp", 0)
        
        logger.info("Processing LINE event", 
                   type=event_type, 
                   user_id=user_id,
                   timestamp=timestamp)
        
        # Record event metric
        await self._record_event_metric(event_type, user_id)
        
        try:
            if event_type == "message":
                return await self._handle_message_event(event_data)
            elif event_type == "follow":
                return await self._handle_follow_event(event_data)
            elif event_type == "unfollow":
                return await self._handle_unfollow_event(event_data)
            elif event_type == "postback":
                return await self._handle_postback_event(event_data)
            else:
                logger.info("Unhandled LINE event type", type=event_type)
                return {"success": True, "message": f"Event type '{event_type}' not handled"}
                
        except Exception as e:
            logger.error("Event processing failed", type=event_type, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _handle_message_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle LINE message event."""
        
        user_id = event_data.get("source", {}).get("userId")
        message = event_data.get("message", {})
        message_type = message.get("type")
        
        if message_type != "text":
            logger.info("Non-text message received", type=message_type, user_id=user_id)
            return {"success": True, "message": f"Message type '{message_type}' not handled"}
        
        user_message = message.get("text", "")
        
        logger.info("Processing text message", user_id=user_id, message_length=len(user_message))
        
        try:
            # Get or create customer profile
            await self._update_customer_interaction(user_id)
            
            # Process message for customer information extraction
            from ..customers.manager import customer_manager
            extraction_result = await customer_manager.process_message_for_extraction(user_id, user_message)
            
            # Check cache first
            from ..cache.manager import cache_manager
            context_data = {"user_id": user_id}
            cached_response, cache_type = await cache_manager.get_cached_response(user_message, context_data)
            
            if cached_response:
                logger.info("Using cached response", 
                           user_id=user_id, 
                           cache_type=cache_type,
                           response_length=len(cached_response))
                
                ai_response_content = cached_response
                ai_provider = f"cache_{cache_type}"
                tokens_used = 0
            else:
                # Get conversation history with dynamic instructions
                conversation = await self._get_conversation_history(user_id, user_message)
                
                # Add user message to conversation
                conversation.append(AIMessage(role="user", content=user_message))
                
                # Generate AI response
                ai_response = await ai_manager.generate_response(conversation)
                ai_response_content = ai_response.content
                ai_provider = ai_response.provider
                tokens_used = ai_response.usage.get("total_tokens", 0)
                
                # Cache the response
                await cache_manager.cache_response(
                    user_message,
                    ai_response_content,
                    context_data,
                    ai_provider,
                    tokens_used
                )
            
            # Store conversation
            await self._store_conversation_turn(user_id, user_message, ai_response_content)
            
            # Send reply to LINE
            reply_success = await self._send_reply(
                event_data.get("replyToken"),
                ai_response_content
            )
            
            logger.info("Message processed", 
                       user_id=user_id, 
                       provider=ai_provider,
                       response_length=len(ai_response_content),
                       reply_sent=reply_success,
                       extraction_changes=len(extraction_result.get("changes", [])),
                       tokens_used=tokens_used)
            
            return {
                "success": True,
                "user_id": user_id,
                "message_processed": True,
                "ai_provider": ai_provider,
                "reply_sent": reply_success,
                "response_length": len(ai_response_content),
                "tokens_used": tokens_used,
                "extraction_changes": extraction_result.get("changes", [])
            }
            
        except Exception as e:
            logger.error("Message handling failed", user_id=user_id, error=str(e))
            
            # Try to send error message
            try:
                await self._send_reply(
                    event_data.get("replyToken"),
                    "ขออภัย เกิดข้อผิดพลาดในระบบ กรุณาลองใหม่ภายหลัง"
                )
            except:
                pass
            
            return {"success": False, "error": str(e)}
    
    async def _handle_follow_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle LINE follow event."""
        
        user_id = event_data.get("source", {}).get("userId")
        
        logger.info("User followed bot", user_id=user_id)
        
        try:
            # Create/update customer profile
            await self._create_customer_profile(user_id)
            
            # Send welcome message
            welcome_message = (
                "ยินดีต้อนรับสู่บริการ 3D Printing ของเรา! 🎯\n\n"
                "เราสามารถช่วยคุณได้ในเรื่อง:\n"
                "• คำแนะนำเกี่ยวกับการพิมพ์ 3D\n"
                "• ราคาและบริการต่างๆ\n" 
                "• การแก้ไขปัญหา\n"
                "• คำถามทั่วไป\n\n"
                "พิมพ์ข้อความมาได้เลยครับ!"
            )
            
            reply_success = await self._send_reply(
                event_data.get("replyToken"),
                welcome_message
            )
            
            return {
                "success": True,
                "user_id": user_id,
                "action": "follow",
                "welcome_sent": reply_success
            }
            
        except Exception as e:
            logger.error("Follow event handling failed", user_id=user_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _handle_unfollow_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle LINE unfollow event."""
        
        user_id = event_data.get("source", {}).get("userId")
        
        logger.info("User unfollowed bot", user_id=user_id)
        
        try:
            # Update customer status
            await self._update_customer_status(user_id, "unfollowed")
            
            return {
                "success": True,
                "user_id": user_id,
                "action": "unfollow"
            }
            
        except Exception as e:
            logger.error("Unfollow event handling failed", user_id=user_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _handle_postback_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle LINE postback event."""
        
        user_id = event_data.get("source", {}).get("userId")
        postback_data = event_data.get("postback", {}).get("data", "")
        
        logger.info("Postback event received", user_id=user_id, data=postback_data)
        
        # TODO: Implement postback handling for interactive features
        
        return {
            "success": True,
            "user_id": user_id,
            "action": "postback",
            "data": postback_data
        }
    
    async def _get_conversation_history(self, user_id: str, current_message: str = "", limit: int = 10) -> List[AIMessage]:
        """Get conversation history for user."""
        
        try:
            # Get conversation from Redis
            conversation_key = f"conversation:{user_id}"
            conversation_data = await redis_client.lrange(conversation_key, -limit * 2, -1)
            
            messages = []
            
            # Extract conversation history for context
            history_messages = []
            for msg_data in conversation_data:
                try:
                    msg_json = json.loads(msg_data)
                    history_messages.append(msg_json.get("content", ""))
                except json.JSONDecodeError:
                    continue
            
            # Add dynamic system instruction
            system_instruction = await self._get_system_instruction(user_id, current_message, history_messages)
            if system_instruction:
                messages.append(AIMessage(role="system", content=system_instruction))
            
            # Parse stored messages
            for msg_data in conversation_data:
                try:
                    msg_json = json.loads(msg_data)
                    messages.append(AIMessage(
                        role=msg_json.get("role"),
                        content=msg_json.get("content")
                    ))
                except json.JSONDecodeError:
                    continue
            
            return messages
            
        except Exception as e:
            logger.warning("Failed to get conversation history", user_id=user_id, error=str(e))
            
            # Return default system message
            system_instruction = await self._get_system_instruction(user_id, current_message, [])
            if system_instruction:
                return [AIMessage(role="system", content=system_instruction)]
            else:
                return []
    
    async def _get_system_instruction(self, user_id: str, user_message: str = "", conversation_history: List[str] = None) -> str:
        """Get dynamic system instruction for user."""
        
        try:
            # Use dynamic instruction system
            from ..instructions.manager import instruction_manager
            dynamic_instruction = await instruction_manager.generate_dynamic_instructions(
                user_id, user_message, conversation_history or []
            )
            return dynamic_instruction
            
        except Exception as e:
            logger.warning("Failed to get dynamic instruction", user_id=user_id, error=str(e))
            
            # Fallback to default instruction
            default_instruction = """คุณคือผู้ช่วย AI สำหรับธุรกิจ 3D Printing ในประเทศไทย

บทบาทของคุณ:
- ให้คำแนะนำเกี่ยวกับการพิมพ์ 3D, วัสดุ, และเทคนิค
- ตอบคำถามเกี่ยวกับราคาและบริการต่างๆ
- แก้ไขปัญหาทางเทคนิค
- ให้ข้อมูลเกี่ยวกับผลิตภัณฑ์และการใช้งาน

คำแนะนำการตอบ:
- ใช้ภาษาไทยที่เป็นมิตรและเข้าใจง่าย
- ให้ข้อมูลที่แม่นยำและเป็นประโยชน์
- หากไม่แน่ใจ ให้แนะนำให้ติดต่อทีมงานโดยตรง
- ใช้อีโมจิให้เหมาะสมเพื่อให้การสนทนาน่าสนใจ"""
            
            return default_instruction
    
    async def _store_conversation_turn(self, user_id: str, user_message: str, ai_response: str):
        """Store conversation turn in Redis."""
        
        try:
            conversation_key = f"conversation:{user_id}"
            
            # Create message objects
            user_msg = {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            ai_msg = {
                "role": "assistant", 
                "content": ai_response,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Store messages
            await redis_client.rpush(conversation_key, json.dumps(user_msg))
            await redis_client.rpush(conversation_key, json.dumps(ai_msg))
            
            # Keep only last 50 messages (25 turns)
            await redis_client.ltrim(conversation_key, -50, -1)
            
            # Set expiration (30 days)
            await redis_client.expire(conversation_key, 30 * 24 * 60 * 60)
            
        except Exception as e:
            logger.warning("Failed to store conversation", user_id=user_id, error=str(e))
    
    async def _send_reply(self, reply_token: str, message: str) -> bool:
        """Send reply message to LINE."""
        
        if not reply_token:
            logger.warning("Cannot send reply: missing reply token")
            return False
        
        try:
            # Initialize LINE client if needed
            if not line_client._initialized:
                await line_client.initialize()
            
            # Create text message
            text_message = line_client.create_text_message(message)
            
            # Send reply
            success = await line_client.send_reply_message(reply_token, [text_message])
            
            logger.info("Reply sent", 
                       reply_token=reply_token, 
                       message_length=len(message),
                       success=success)
            
            return success
            
        except Exception as e:
            logger.error("Failed to send reply", 
                        reply_token=reply_token, 
                        error=str(e))
            return False
    
    async def _update_customer_interaction(self, user_id: str):
        """Update customer last interaction time."""
        
        try:
            customer_key = f"customer:{user_id}"
            await redis_client.hset(customer_key, "last_interaction", datetime.utcnow().isoformat())
            
        except Exception as e:
            logger.warning("Failed to update customer interaction", user_id=user_id, error=str(e))
    
    async def _create_customer_profile(self, user_id: str):
        """Create basic customer profile."""
        
        try:
            customer_key = f"customer:{user_id}"
            
            # Check if profile exists
            exists = await redis_client.exists(customer_key)
            if exists:
                # Update last interaction
                await self._update_customer_interaction(user_id)
                return
            
            # Create new profile
            now = datetime.utcnow().isoformat()
            profile_data = {
                "user_id": user_id,
                "status": "active",
                "created_at": now,
                "last_interaction": now,
                "message_count": "0",
                "source": "line"
            }
            
            for field, value in profile_data.items():
                await redis_client.hset(customer_key, field, value)
            
            logger.info("Customer profile created", user_id=user_id)
            
        except Exception as e:
            logger.error("Failed to create customer profile", user_id=user_id, error=str(e))
    
    async def _update_customer_status(self, user_id: str, status: str):
        """Update customer status."""
        
        try:
            customer_key = f"customer:{user_id}"
            await redis_client.hset(customer_key, "status", status)
            await redis_client.hset(customer_key, "updated_at", datetime.utcnow().isoformat())
            
        except Exception as e:
            logger.warning("Failed to update customer status", user_id=user_id, error=str(e))
    
    async def _record_event_metric(self, event_type: str, user_id: str):
        """Record event metric for monitoring."""
        
        try:
            timestamp = datetime.utcnow().isoformat()
            metric_key = f"metric:line_event:{timestamp}"
            
            metric_data = {
                "event_type": event_type,
                "user_id": user_id or "unknown",
                "timestamp": timestamp
            }
            
            for field, value in metric_data.items():
                await redis_client.hset(metric_key, field, value)
            
            # Set expiration (7 days)
            await redis_client.expire(metric_key, 7 * 24 * 60 * 60)
            
        except Exception as e:
            logger.warning("Failed to record event metric", error=str(e))


# Global webhook handler instance
line_webhook_handler = LineWebhookHandler()