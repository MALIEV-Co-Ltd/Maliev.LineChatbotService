"""Unit tests for LINE webhook handler using mocks."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastapi import HTTPException

from src.line.webhook import LineWebhookHandler
from src.line.models import MessageEvent, FollowEvent


@pytest.mark.unit
class TestLineWebhookUnit:
    """Unit tests for LINE webhook handler."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies."""
        return {
            'redis_client': AsyncMock(),
            'secret_manager': AsyncMock(),
            'ai_manager': AsyncMock(),
            'customer_manager': AsyncMock(),
            'instruction_manager': AsyncMock(),
            'cache_manager': AsyncMock(),
            'line_client': AsyncMock()
        }
    
    @pytest.fixture
    def webhook_handler(self, mock_dependencies):
        """Webhook handler with mocked dependencies."""
        with patch.multiple(
            'src.line.webhook',
            redis_client=mock_dependencies['redis_client'],
            secret_manager=mock_dependencies['secret_manager'],
            ai_manager=mock_dependencies['ai_manager'],
        ):
            handler = LineWebhookHandler()
            handler._channel_secret = "test-secret"
            handler._access_token = "test-token"
            return handler
    
    @pytest.fixture
    def valid_line_request(self):
        """Valid LINE webhook request data."""
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
                        "userId": "test-user-id"
                    },
                    "message": {
                        "id": "test-message-id",
                        "type": "text",
                        "text": "Hello, bot!"
                    },
                    "webhookEventId": "test-webhook-event-id",
                    "deliveryContext": {
                        "isRedelivery": False
                    }
                }
            ]
        }
    
    @pytest.fixture  
    def complete_message_event_data(self):
        """Complete message event data for testing."""
        return {
            "replyToken": "test-reply-token",
            "type": "message",
            "timestamp": 1234567890123,
            "source": {"type": "user", "userId": "test-user-id"},
            "message": {
                "id": "test-message-id", 
                "type": "text", 
                "text": "Hello"
            },
            "webhookEventId": "test-webhook-event-id"
        }
    
    @pytest.fixture
    def complete_follow_event_data(self):
        """Complete follow event data for testing."""
        return {
            "replyToken": "test-reply-token",
            "type": "follow",
            "timestamp": 1234567890123,
            "source": {"type": "user", "userId": "test-user-id"},
            "webhookEventId": "test-webhook-event-id"
        }
    
    def test_signature_verification_valid(self, webhook_handler):
        """Test valid signature verification."""
        body = b'{"test": "data"}'
        # Create valid signature using HMAC-SHA256
        import hmac
        import hashlib
        import base64
        
        signature = base64.b64encode(
            hmac.new(
                "test-secret".encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        result = webhook_handler._verify_signature(body, signature)
        assert result is True
    
    def test_signature_verification_invalid(self, webhook_handler):
        """Test invalid signature verification."""
        body = b'{"test": "data"}'
        invalid_signature = "invalid-signature"
        
        result = webhook_handler._verify_signature(body, invalid_signature)
        assert result is False
    
    def test_signature_verification_development_bypass(self):
        """Test signature verification bypass in development mode."""
        with patch('src.line.webhook.settings') as mock_settings:
            mock_settings.environment = "development"
            
            handler = LineWebhookHandler()
            # No channel secret configured
            result = handler._verify_signature(b'test', "any-signature")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_handle_webhook_missing_signature(self, webhook_handler):
        """Test webhook handling with missing signature header."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.body.return_value = b'{"events": []}'
        
        with pytest.raises(HTTPException) as exc:
            await webhook_handler.handle_webhook(mock_request)
        
        assert exc.value.status_code == 400
        assert "Missing signature header" in str(exc.value.detail)
    
    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_signature(self, webhook_handler):
        """Test webhook handling with invalid signature."""
        mock_request = MagicMock()
        mock_request.headers = {"x-line-signature": "invalid-signature"}
        mock_request.body.return_value = b'{"events": []}'
        
        with pytest.raises(HTTPException) as exc:
            await webhook_handler.handle_webhook(mock_request)
        
        assert exc.value.status_code == 400
        assert "Invalid signature" in str(exc.value.detail)
    
    @pytest.mark.asyncio
    async def test_handle_webhook_success(self, webhook_handler, valid_line_request):
        """Test successful webhook handling."""
        mock_request = MagicMock()
        mock_request.headers = {"x-line-signature": "valid-signature"}
        body = json.dumps(valid_line_request).encode()
        mock_request.body.return_value = body
        
        # Mock signature verification to pass
        webhook_handler._verify_signature = MagicMock(return_value=True)
        
        # Mock event processing
        with patch.object(webhook_handler, '_process_events') as mock_process:
            mock_process.return_value = None
            
            result = await webhook_handler.handle_webhook(mock_request)
            
            assert result == {"status": "ok"}
            mock_process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_event(self, webhook_handler, mock_dependencies, complete_message_event_data):
        """Test processing message events."""
        event_data = complete_message_event_data
        
        # Mock AI response
        mock_dependencies['ai_manager'].generate_response.return_value = "Hi there!"
        
        with patch.object(webhook_handler, '_send_reply') as mock_send:
            mock_send.return_value = True
            
            await webhook_handler._handle_message_event(MessageEvent(**event_data))
            
            mock_send.assert_called_once_with("test-reply-token", "Hi there!")
    
    @pytest.mark.asyncio
    async def test_process_follow_event(self, webhook_handler, mock_dependencies, complete_follow_event_data):
        """Test processing follow events."""
        event_data = complete_follow_event_data
        
        with patch.object(webhook_handler, '_send_reply') as mock_send:
            mock_send.return_value = True
            
            await webhook_handler._handle_follow_event(FollowEvent(**event_data))
            
            # Should send welcome message
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert "Welcome" in args[1] or "welcome" in args[1]
    
    def test_extract_user_info_message_event(self, webhook_handler, complete_message_event_data):
        """Test extracting user info from message events."""
        event_data = complete_message_event_data.copy()
        event_data["message"]["text"] = "My name is John Doe"
        
        event = MessageEvent(**event_data)
        user_info = webhook_handler._extract_user_info(event)
        
        assert user_info["user_id"] == "test-user-id"
        assert user_info["source_type"] == "user"
        assert user_info["message_text"] == "My name is John Doe"
    
    @pytest.mark.asyncio
    async def test_error_handling_ai_failure(self, webhook_handler, mock_dependencies, complete_message_event_data):
        """Test error handling when AI provider fails."""
        event_data = complete_message_event_data
        
        # Mock AI failure
        mock_dependencies['ai_manager'].generate_response.side_effect = Exception("AI Error")
        
        with patch.object(webhook_handler, '_send_reply') as mock_send:
            mock_send.return_value = True
            
            await webhook_handler._handle_message_event(MessageEvent(**event_data))
            
            # Should send error message
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert "sorry" in args[1].lower() or "error" in args[1].lower()