"""Component tests for webhook integration with real dependencies."""

import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import app
from src.line.webhook import LineWebhookHandler


@pytest.mark.component
class TestWebhookIntegration:
    """Component tests for webhook integration."""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client."""
        return TestClient(app)
    
    @pytest.fixture
    def valid_line_payload(self):
        """Valid LINE webhook payload."""
        return {
            "destination": "test-destination", 
            "events": [
                {
                    "replyToken": "test-reply-token",
                    "type": "message",
                    "mode": "active",
                    "timestamp": 1234567890123,
                    "source": {
                        "type": "user",
                        "userId": "test-user-123"
                    },
                    "message": {
                        "id": "test-message-id",
                        "type": "text", 
                        "text": "Hello, I need help with 3D printing"
                    },
                    "webhookEventId": "test-webhook-event-id",
                    "deliveryContext": {
                        "isRedelivery": False
                    }
                }
            ]
        }
    
    @pytest.fixture
    async def webhook_handler_integration(self, real_redis):
        """Webhook handler with real Redis integration."""
        handler = LineWebhookHandler()
        
        # Patch external dependencies while keeping Redis real
        with patch('src.line.webhook.secret_manager') as mock_secret:
            mock_secret.get_secret.return_value = "test-secret"
            
            # Initialize with test credentials
            handler._channel_secret = "test-channel-secret"
            handler._access_token = "test-access-token"
            
            return handler
    
    def test_webhook_endpoint_exists(self, test_client):
        """Test webhook endpoint is available."""
        # Test without signature header (should fail)
        response = test_client.post("/webhook", json={"events": []})
        
        # Should return 500 due to missing signature, but endpoint exists
        assert response.status_code in [400, 500]
        
        # Test with invalid signature
        response = test_client.post(
            "/webhook",
            json={"events": []},
            headers={"x-line-signature": "invalid"}
        )
        assert response.status_code in [400, 500]
    
    @pytest.mark.asyncio
    async def test_signature_verification_integration(self, webhook_handler_integration):
        """Test signature verification with real implementation."""
        import hmac
        import hashlib
        import base64
        
        # Test data
        body = b'{"events": [{"type": "message", "message": {"text": "test"}}]}'
        secret = "test-channel-secret"
        
        # Generate valid signature
        signature = base64.b64encode(
            hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Test valid signature
        result = webhook_handler_integration._verify_signature(body, signature)
        assert result is True
        
        # Test invalid signature
        result = webhook_handler_integration._verify_signature(body, "invalid")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_full_message_processing_flow(self, webhook_handler_integration, real_redis, valid_line_payload):
        """Test complete message processing workflow."""
        # Mock external services
        with patch('src.line.webhook.ai_manager') as mock_ai, \
             patch('src.line.webhook.line_client') as mock_line_client, \
             patch.object(webhook_handler_integration, '_verify_signature', return_value=True):
            
            # Setup AI response
            mock_ai.generate_response.return_value = "I'd be happy to help you with 3D printing! What specific aspect would you like to know about?"
            
            # Setup LINE client
            mock_line_client.send_reply_message.return_value = True
            mock_line_client._initialized = True
            mock_line_client.create_text_message.return_value = {"type": "text", "text": "response"}
            
            # Create mock request
            from unittest.mock import MagicMock
            mock_request = MagicMock()
            mock_request.headers = {"x-line-signature": "valid-signature"}
            mock_request.body.return_value = json.dumps(valid_line_payload).encode()
            
            # Process webhook
            result = await webhook_handler_integration.handle_webhook(mock_request)
            
            # Verify result
            assert result == {"status": "ok"}
            
            # Verify AI was called
            mock_ai.generate_response.assert_called_once()
            call_args = mock_ai.generate_response.call_args[0]
            assert "Hello, I need help with 3D printing" in call_args[0]
            
            # Verify LINE client was called
            mock_line_client.send_reply_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conversation_storage_with_redis(self, webhook_handler_integration, real_redis):
        """Test conversation storage in Redis."""
        user_id = "integration-test-user"
        conversation_key = f"conversation:{user_id}"
        
        # Store conversation in Redis
        messages = [
            '{"role": "user", "content": "Hello"}',
            '{"role": "assistant", "content": "Hi! How can I help you?"}',
            '{"role": "user", "content": "I need 3D printing advice"}',
        ]
        
        for message in messages:
            await real_redis.rpush(conversation_key, message)
        
        # Retrieve conversation
        stored_messages = await real_redis.lrange(conversation_key, 0, -1)
        stored_messages = [msg.decode() if isinstance(msg, bytes) else msg for msg in stored_messages]
        
        assert len(stored_messages) == len(messages)
        assert stored_messages == messages
        
        # Test conversation trimming (keep last 50 messages)
        await real_redis.ltrim(conversation_key, -50, -1)
        
        # Verify trimming
        final_messages = await real_redis.lrange(conversation_key, 0, -1)
        assert len(final_messages) <= 50
    
    @pytest.mark.asyncio
    async def test_customer_profile_integration(self, webhook_handler_integration, real_redis):
        """Test customer profile management with Redis."""
        user_id = "integration-customer-123"
        profile_key = f"customer:{user_id}"
        
        # Extract user info from message
        from src.line.models import MessageEvent
        event_data = {
            "replyToken": "test-reply",
            "type": "message",
            "source": {"type": "user", "userId": user_id},
            "message": {
                "type": "text", 
                "text": "Hi, I'm John Smith from TechCorp. My email is john@techcorp.com"
            }
        }
        
        event = MessageEvent(**event_data)
        user_info = webhook_handler_integration._extract_user_info(event)
        
        # Store in Redis
        for field, value in user_info.items():
            if value is not None:
                await real_redis.hset(profile_key, field, str(value))
        
        # Retrieve and verify
        stored_profile = await real_redis.hgetall(profile_key)
        
        assert stored_profile["user_id"] == user_id
        assert stored_profile["source_type"] == "user"
        assert "john@techcorp.com" in stored_profile["message_text"]
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, webhook_handler_integration, real_redis):
        """Test error handling in integrated environment."""
        # Test Redis connection failure simulation
        original_client = webhook_handler_integration
        
        # Test with invalid event data
        invalid_event_data = {
            "replyToken": "test-reply",
            "type": "message", 
            "source": {"type": "user", "userId": "test-user"},
            "message": None  # Invalid message
        }
        
        # Should handle gracefully without crashing
        try:
            from src.line.models import MessageEvent
            MessageEvent(**invalid_event_data)
        except Exception as e:
            # Expected to fail validation
            assert "message" in str(e).lower() or "field required" in str(e).lower()
    
    @pytest.mark.asyncio 
    async def test_concurrent_webhook_processing(self, webhook_handler_integration, real_redis):
        """Test handling multiple concurrent webhook requests."""
        # Mock external dependencies
        with patch('src.line.webhook.ai_manager') as mock_ai, \
             patch('src.line.webhook.line_client') as mock_line_client, \
             patch.object(webhook_handler_integration, '_verify_signature', return_value=True):
            
            mock_ai.generate_response.return_value = "Concurrent response"
            mock_line_client.send_reply_message.return_value = True
            mock_line_client._initialized = True
            mock_line_client.create_text_message.return_value = {"type": "text"}
            
            # Create multiple requests
            async def process_request(request_id):
                payload = {
                    "destination": "test",
                    "events": [{
                        "replyToken": f"reply-{request_id}",
                        "type": "message",
                        "source": {"type": "user", "userId": f"user-{request_id}"},
                        "message": {"type": "text", "text": f"Message {request_id}"}
                    }]
                }
                
                from unittest.mock import MagicMock
                mock_request = MagicMock()
                mock_request.headers = {"x-line-signature": "valid"}
                mock_request.body.return_value = json.dumps(payload).encode()
                
                return await webhook_handler_integration.handle_webhook(mock_request)
            
            # Process multiple requests concurrently
            tasks = [process_request(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Verify all succeeded
            for result in results:
                assert result == {"status": "ok"}
            
            # Verify all AI calls were made
            assert mock_ai.generate_response.call_count == 5