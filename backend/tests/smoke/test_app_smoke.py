"""Smoke tests for application health and basic functionality."""

import pytest
import requests
import json
import time
from unittest.mock import patch


@pytest.mark.smoke
class TestApplicationSmoke:
    """Smoke tests - verify application is running and responsive."""
    
    @pytest.fixture(scope="class")
    def base_url(self):
        """Base URL for the application."""
        return "http://127.0.0.1:8000"
    
    def test_application_starts(self, base_url):
        """Test that the application starts and responds."""
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("Application not running - start with: uvicorn src.main:app --reload")
    
    def test_health_endpoint(self, base_url):
        """Test health endpoint returns correct information."""
        response = requests.get(f"{base_url}/health", timeout=5)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert data["status"] == "healthy"
    
    def test_api_documentation_available(self, base_url):
        """Test that API documentation is available."""
        # Test Swagger UI
        response = requests.get(f"{base_url}/docs", timeout=5)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        # Test OpenAPI schema
        response = requests.get(f"{base_url}/openapi.json", timeout=5)
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/webhook" in schema["paths"]
    
    def test_webhook_endpoint_exists(self, base_url):
        """Test webhook endpoint is available (even if it fails validation)."""
        response = requests.post(
            f"{base_url}/webhook", 
            json={"events": []},
            timeout=5
        )
        
        # Should return 400 or 500 (missing signature), not 404
        assert response.status_code in [400, 500]
        assert response.status_code != 404  # Endpoint exists
    
    def test_cors_headers(self, base_url):
        """Test CORS headers are properly configured."""
        response = requests.options(
            f"{base_url}/health",
            headers={"Origin": "http://localhost:3000"},
            timeout=5
        )
        
        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
    
    def test_application_info_endpoint(self, base_url):
        """Test application info endpoint."""
        response = requests.get(f"{base_url}/", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "Maliev LINE Chatbot Service"


@pytest.mark.smoke
@pytest.mark.slow
class TestExternalDependenciesSmoke:
    """Smoke tests for external dependencies."""
    
    @pytest.mark.asyncio
    async def test_redis_connection(self, smoke_redis):
        """Test Redis connection works."""
        # Basic ping test
        result = await smoke_redis.ping()
        assert result is True
        
        # Basic set/get test
        await smoke_redis.set("smoke_test", "success")
        result = await smoke_redis.get("smoke_test")
        assert result == "success"
        
        # Cleanup
        await smoke_redis.delete("smoke_test")
    
    @pytest.mark.asyncio
    async def test_redis_performance(self, smoke_redis):
        """Test Redis basic performance."""
        start_time = time.time()
        
        # Perform 100 set operations
        for i in range(100):
            await smoke_redis.set(f"perf_test_{i}", f"value_{i}")
        
        # Perform 100 get operations
        for i in range(100):
            result = await smoke_redis.get(f"perf_test_{i}")
            assert result == f"value_{i}"
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 200 operations in reasonable time (< 2 seconds)
        assert duration < 2.0, f"Redis operations took {duration:.2f}s, expected < 2.0s"
        
        # Cleanup
        keys = [f"perf_test_{i}" for i in range(100)]
        await smoke_redis.delete(*keys)


@pytest.mark.smoke
class TestWebhookFlowSmoke:
    """Smoke tests for webhook processing flow."""
    
    @pytest.fixture
    def base_url(self):
        return "http://127.0.0.1:8000"
    
    def test_webhook_signature_validation(self, base_url):
        """Test webhook signature validation works."""
        # Test missing signature
        response = requests.post(
            f"{base_url}/webhook",
            json={"events": []},
            timeout=5
        )
        
        # Should return 400 for missing signature (not crash)
        assert response.status_code == 400
        
        # Test invalid signature
        response = requests.post(
            f"{base_url}/webhook",
            json={"events": []},
            headers={"x-line-signature": "invalid-signature"},
            timeout=5
        )
        
        # Should return 400 for invalid signature (not crash)
        assert response.status_code == 400
    
    def test_webhook_development_mode(self, base_url):
        """Test webhook works in development mode."""
        # In development mode, signature verification should be bypassed
        # when no channel secret is configured
        
        valid_payload = {
            "destination": "test",
            "events": [{
                "replyToken": "smoke-test-reply-token",
                "type": "message",
                "source": {"type": "user", "userId": "smoke-test-user"},
                "message": {"type": "text", "text": "smoke test message"}
            }]
        }
        
        # This should work in development mode even without proper signature
        response = requests.post(
            f"{base_url}/webhook",
            json=valid_payload,
            headers={"x-line-signature": "development-bypass"},
            timeout=10  # Longer timeout as it processes the event
        )
        
        # Should either succeed (200) or have controlled error (400/500)
        # Should NOT return 404 or crash
        assert response.status_code in [200, 400, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data


@pytest.mark.smoke
class TestErrorHandlingSmoke:
    """Smoke tests for error handling."""
    
    @pytest.fixture 
    def base_url(self):
        return "http://127.0.0.1:8000"
    
    def test_malformed_json_handling(self, base_url):
        """Test application handles malformed JSON gracefully."""
        response = requests.post(
            f"{base_url}/webhook",
            data="invalid json",
            headers={
                "content-type": "application/json",
                "x-line-signature": "test"
            },
            timeout=5
        )
        
        # Should return 400 (bad request), not crash
        assert response.status_code == 400
    
    def test_large_payload_handling(self, base_url):
        """Test application handles large payloads."""
        # Create large payload
        large_text = "x" * 10000  # 10KB text
        large_payload = {
            "destination": "test",
            "events": [{
                "replyToken": "large-test",
                "type": "message", 
                "source": {"type": "user", "userId": "test-user"},
                "message": {"type": "text", "text": large_text}
            }]
        }
        
        response = requests.post(
            f"{base_url}/webhook",
            json=large_payload,
            headers={"x-line-signature": "test"},
            timeout=10
        )
        
        # Should handle gracefully (not timeout or crash)
        assert response.status_code in [200, 400, 500]
    
    def test_concurrent_requests(self, base_url):
        """Test application handles concurrent requests."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request(request_id):
            try:
                response = requests.get(f"{base_url}/health", timeout=5)
                results.put((request_id, response.status_code))
            except Exception as e:
                results.put((request_id, f"error: {e}"))
        
        # Make 10 concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all requests
        for thread in threads:
            thread.join()
        
        # Check all requests succeeded
        success_count = 0
        while not results.empty():
            request_id, status = results.get()
            if status == 200:
                success_count += 1
        
        # At least 80% should succeed (allowing for some concurrency issues)
        assert success_count >= 8, f"Only {success_count}/10 concurrent requests succeeded"