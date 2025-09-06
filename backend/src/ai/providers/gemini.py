"""Google Gemini AI provider implementation."""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime

import httpx
import structlog

from ..base import (
    AIProvider, 
    AIMessage, 
    AIResponse, 
    AIConfiguration,
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderQuotaError,
    AIProviderAuthError
)

logger = structlog.get_logger("ai.gemini")


class GeminiProvider(AIProvider):
    """Google Gemini AI provider implementation."""
    
    def __init__(self, config: AIConfiguration):
        """Initialize Gemini provider."""
        super().__init__(config)
        
        # Gemini API configuration
        self.base_url = config.base_url or "https://generativelanguage.googleapis.com"
        self.api_version = "v1beta"
        
        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": config.api_key
            }
        )
        
        # Model-specific settings
        self.model_name = config.model or "gemini-2.5-flash"
        
    async def generate_response(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AIResponse:
        """Generate response from Gemini."""
        
        try:
            start_time = datetime.utcnow()
            
            # Prepare request payload
            payload = self._prepare_payload(messages, **kwargs)
            
            # Make API request
            url = f"{self.base_url}/{self.api_version}/models/{self.model_name}:generateContent"
            
            self.logger.debug("Making Gemini API request", url=url, model=self.model_name)
            
            response = await self.client.post(url, json=payload)
            
            # Handle HTTP errors
            if response.status_code == 401:
                raise AIProviderAuthError("Invalid API key", self.name)
            elif response.status_code == 429:
                raise AIProviderQuotaError("Rate limit exceeded", self.name)
            elif response.status_code >= 400:
                error_detail = response.text
                raise AIProviderError(f"API error: {error_detail}", self.name, str(response.status_code))
            
            # Parse response
            response_data = response.json()
            
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # Extract content and metadata
            content = self._extract_content(response_data)
            usage = self._extract_usage(response_data)
            finish_reason = self._extract_finish_reason(response_data)
            
            self.logger.info("Gemini response generated", 
                           response_time_ms=response_time_ms,
                           tokens=usage.get("total_tokens", 0))
            
            return self.create_response(
                content=content,
                usage=usage,
                finish_reason=finish_reason,
                response_time_ms=response_time_ms,
                metadata={
                    "model": self.model_name,
                    "raw_response": response_data
                }
            )
            
        except httpx.TimeoutException:
            raise AIProviderTimeoutError("Request timeout", self.name)
        except httpx.RequestError as e:
            raise AIProviderError(f"Request failed: {str(e)}", self.name)
        except Exception as e:
            self.logger.error("Gemini request failed", error=str(e), exc_info=e)
            raise AIProviderError(f"Unexpected error: {str(e)}", self.name)
    
    async def generate_stream_response(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response from Gemini."""
        
        try:
            # Prepare request payload for streaming
            payload = self._prepare_payload(messages, stream=True, **kwargs)
            
            url = f"{self.base_url}/{self.api_version}/models/{self.model_name}:streamGenerateContent"
            
            self.logger.debug("Making Gemini streaming request", url=url, model=self.model_name)
            
            async with self.client.stream("POST", url, json=payload) as response:
                if response.status_code >= 400:
                    error_detail = await response.aread()
                    raise AIProviderError(f"Streaming API error: {error_detail.decode()}", self.name)
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            # Parse JSON line
                            chunk_data = json.loads(line)
                            
                            # Extract content from chunk
                            chunk_content = self._extract_streaming_content(chunk_data)
                            if chunk_content:
                                yield chunk_content
                                
                        except json.JSONDecodeError:
                            # Skip non-JSON lines
                            continue
                        except Exception as e:
                            self.logger.warning("Failed to process stream chunk", error=str(e))
                            continue
            
        except httpx.TimeoutException:
            raise AIProviderTimeoutError("Streaming request timeout", self.name)
        except httpx.RequestError as e:
            raise AIProviderError(f"Streaming request failed: {str(e)}", self.name)
        except Exception as e:
            self.logger.error("Gemini streaming failed", error=str(e))
            raise AIProviderError(f"Streaming error: {str(e)}", self.name)
    
    async def health_check(self) -> bool:
        """Check Gemini API health."""
        try:
            # Simple test request
            test_messages = [
                AIMessage(role="user", content="Hello")
            ]
            
            await asyncio.wait_for(
                self.generate_response(test_messages, max_tokens=10),
                timeout=10.0
            )
            
            return True
            
        except Exception as e:
            self.logger.warning("Gemini health check failed", error=str(e))
            return False
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for Gemini (rough approximation)."""
        # Gemini uses different tokenization, this is a rough estimate
        # For more accuracy, we'd use the actual Gemini tokenizer
        return max(1, len(text) // 4)
    
    def _prepare_payload(self, messages: List[AIMessage], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Prepare API request payload for Gemini."""
        
        # Convert messages to Gemini format
        contents = []
        system_instruction = None
        
        for message in messages:
            if message.role == "system":
                # Gemini handles system messages differently
                system_instruction = {
                    "parts": [{"text": message.content}]
                }
            else:
                # Map roles
                role = "user" if message.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": message.content}]
                })
        
        # Build payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "maxOutputTokens": kwargs.get("max_tokens", self.config.max_tokens),
                "topP": kwargs.get("top_p", 0.95),
                "topK": kwargs.get("top_k", 64),
            }
        }
        
        # Add system instruction if present
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        
        # Add safety settings (optional)
        payload["safetySettings"] = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH", 
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
        
        return payload
    
    def _extract_content(self, response_data: Dict[str, Any]) -> str:
        """Extract content from Gemini response."""
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                return ""
            
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                return ""
            
            # Combine all text parts
            text_parts = [part.get("text", "") for part in parts if "text" in part]
            return "".join(text_parts)
            
        except Exception as e:
            self.logger.warning("Failed to extract content", error=str(e))
            return ""
    
    def _extract_streaming_content(self, chunk_data: Dict[str, Any]) -> str:
        """Extract content from streaming response chunk."""
        try:
            candidates = chunk_data.get("candidates", [])
            if not candidates:
                return ""
            
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                return ""
            
            # Get text from first part
            return parts[0].get("text", "")
            
        except Exception as e:
            self.logger.warning("Failed to extract streaming content", error=str(e))
            return ""
    
    def _extract_usage(self, response_data: Dict[str, Any]) -> Dict[str, int]:
        """Extract token usage from Gemini response."""
        try:
            usage_metadata = response_data.get("usageMetadata", {})
            
            return {
                "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                "total_tokens": usage_metadata.get("totalTokenCount", 0)
            }
            
        except Exception as e:
            self.logger.warning("Failed to extract usage", error=str(e))
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
    
    def _extract_finish_reason(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Extract finish reason from Gemini response."""
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                return None
            
            candidate = candidates[0]
            return candidate.get("finishReason", "STOP")
            
        except Exception as e:
            self.logger.warning("Failed to extract finish reason", error=str(e))
            return None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()