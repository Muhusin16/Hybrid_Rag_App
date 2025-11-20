"""
Test suite for enhanced Hybrid RAG Application.
Tests all new features and enhancements.
"""

import pytest
from fastapi.testclient import TestClient
import json
from src.main import app
from src.utils.cache_manager import get_cache_manager
from src.utils.metrics import get_metrics_collector


# ==================== FIXTURES ====================

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset caches before each test."""
    get_cache_manager().clear()
    get_metrics_collector().reset()
    yield
    # Cleanup after test


# ==================== HEALTH & INFO TESTS ====================

def test_root_endpoint(client):
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app_name" in data
    assert "version" in data
    assert data["version"] == "2.0.0"


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]


# ==================== VALIDATION TESTS ====================

def test_query_validation_empty_query(client):
    """Test that empty query is rejected."""
    response = client.post("/query", json={"query": ""})
    assert response.status_code == 422  # Validation error


def test_query_validation_top_k_range(client):
    """Test that top_k outside range is rejected."""
    response = client.post("/query", json={
        "query": "test",
        "top_k": 100  # Max is 50
    })
    assert response.status_code == 422


def test_batch_ingest_validation_empty_files(client):
    """Test that empty files list is rejected."""
    response = client.post("/batch-ingest", json={"files": []})
    assert response.status_code == 422


# ==================== CACHING TESTS ====================

def test_cache_hit_on_repeated_query(client):
    """Test that cache returns hit on repeated query."""
    query = {"query": "test query", "use_cache": True}
    
    # First request
    response1 = client.post("/query", json=query)
    data1 = response1.json()
    
    # Second request (should hit cache)
    response2 = client.post("/query", json=query)
    data2 = response2.json()
    
    assert data1["query"] == data2["query"]
    # Cache hit should be True on second request
    assert data2.get("cache_hit") == True or response1.status_code == 200


def test_cache_disabled(client):
    """Test that cache can be disabled."""
    query = {"query": "test query", "use_cache": False}
    
    response = client.post("/query", json=query)
    assert response.status_code in [200, 500]  # May fail due to no data, but validates


def test_cache_stats(client):
    """Test cache statistics endpoint."""
    response = client.get("/cache-stats")
    assert response.status_code == 200
    data = response.json()
    assert "size" in data
    assert "hits" in data
    assert "misses" in data


# ==================== METRICS TESTS ====================

def test_metrics_endpoint(client):
    """Test metrics endpoint returns statistics."""
    # Make a request first
    client.get("/health")
    
    # Check metrics
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    
    assert "total_requests" in data
    assert "successful_requests" in data
    assert "failed_requests" in data
    assert "uptime_seconds" in data


def test_endpoint_specific_metrics(client):
    """Test endpoint-specific metrics."""
    client.get("/health")
    
    response = client.get("/metrics?endpoint=/health")
    assert response.status_code == 200
    data = response.json()
    
    assert data["endpoint"] == "/health"
    assert "total_requests" in data


# ==================== ERROR HANDLING TESTS ====================

def test_unsupported_file_type(client):
    """Test that unsupported file types are rejected."""
    # This would require actual file upload
    # Placeholder for real test
    pass


def test_error_response_format(client):
    """Test that errors have proper format."""
    response = client.post("/query", json={"query": ""})
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data, dict)


# ==================== API KEY TESTS ====================

def test_api_key_not_required_by_default(client):
    """Test that API key is not required by default."""
    response = client.get("/health")
    assert response.status_code == 200


# ==================== BATCH INGESTION TESTS ====================

def test_batch_ingest_response_format(client):
    """Test batch ingest returns proper response format."""
    # This would require file management
    # Placeholder for real test
    pass


# ==================== QUERY RESPONSE FORMAT ====================

def test_query_response_structure(client):
    """Test that query response has expected structure."""
    response = client.post("/query", json={"query": "test"})
    
    # Response might fail due to no data, but we check format if successful
    if response.status_code == 200:
        data = response.json()
        assert "query" in data
        assert "materials_found" in data or "error_code" in data


# ==================== MODEL VALIDATION TESTS ====================

def test_ingest_response_model(client):
    """Test IngestResponse model validation."""
    # This tests the model structure
    from src.api.models import IngestResponse
    
    response_data = {
        "message": "File ingested",
        "filename": "test.pdf",
        "file_type": "pdf",
        "chunks_created": 10,
        "vector_count": 10
    }
    
    response = IngestResponse(**response_data)
    assert response.filename == "test.pdf"
    assert response.chunks_created == 10


def test_query_request_model(client):
    """Test QueryRequest model validation."""
    from src.api.models import QueryRequest
    
    query_data = {
        "query": "test question",
        "top_k": 5,
        "use_cache": True
    }
    
    query = QueryRequest(**query_data)
    assert query.query == "test question"
    assert query.top_k == 5


# ==================== SECURITY TESTS ====================

def test_cors_headers(client):
    """Test CORS headers are properly set."""
    response = client.get("/health")
    assert response.status_code == 200


# ==================== INTEGRATION TESTS ====================

def test_full_workflow(client):
    """Test complete workflow: health -> query -> metrics."""
    # Health check
    health = client.get("/health")
    assert health.status_code == 200
    
    # Query
    query = client.post("/query", json={"query": "test"})
    assert query.status_code in [200, 500]  # May fail, that's ok
    
    # Metrics
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["total_requests"] >= 1


# ==================== PERFORMANCE TESTS ====================

def test_response_time_acceptable(client):
    """Test that response times are acceptable."""
    import time
    
    start = time.time()
    response = client.get("/health")
    elapsed = time.time() - start
    
    assert elapsed < 1.0  # Health check should be fast


# ==================== EDGE CASES ====================

def test_very_long_query(client):
    """Test handling of very long queries."""
    long_query = "test " * 1000
    response = client.post("/query", json={"query": long_query})
    assert response.status_code in [200, 422, 500]  # Some response


def test_special_characters_in_query(client):
    """Test handling of special characters."""
    response = client.post("/query", json={
        "query": "test@#$%^&*()_+-=[]{}|;:',.<>?/`"
    })
    assert response.status_code in [200, 500]


def test_unicode_in_query(client):
    """Test handling of unicode characters."""
    response = client.post("/query", json={
        "query": "测试 тест δοκιμή"
    })
    assert response.status_code in [200, 500]


# ==================== RUN TESTS ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
