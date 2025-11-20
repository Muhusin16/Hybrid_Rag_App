# 🚀 Integration Guide - Enhanced Hybrid RAG Application

## Overview

This guide helps you integrate the new features into your existing workflow or migrate to the enhanced version.

## 📦 What's New

### Major Components
1. **Hybrid Search Engine** - Semantic + keyword retrieval
2. **Caching System** - Response caching with TTL
3. **Metrics Collection** - Request tracking and telemetry
4. **Enhanced Logging** - Structured logs with rotation
5. **Error Handling** - Custom exceptions and validation
6. **API Structure** - Modular routes with Pydantic models

---

## 🔄 Migration Path

### Option 1: Full Replacement (Recommended)

If you want all new features, replace the entire `src/` structure:

```bash
# Backup current version
cp -r src src_backup

# New structure is already set up, just verify:
- src/main.py              ✅ Updated with middleware
- src/api/routes.py        ✨ NEW
- src/api/models.py        ✨ NEW
- src/api/error_handlers.py ✨ NEW
- src/retrieval/search_engine.py ✅ Enhanced
- src/utils/logger.py      ✅ Enhanced
- src/utils/cache_manager.py ✨ NEW
- src/utils/metrics.py     ✨ NEW
```

### Option 2: Gradual Integration

If you prefer to adopt features incrementally:

1. **Add Caching** (No breaking changes)
   ```python
   from src.utils.cache_manager import get_cache_manager
   cache = get_cache_manager()
   
   # Use in existing code
   cached_result = cache.get(query)
   if cached_result:
       return cached_result
   ```

2. **Add Logging** (Drop-in replacement)
   ```python
   from src.utils.logger import get_logger
   logger = get_logger(__name__)
   
   # Use as before
   logger.info("Processing query...")
   ```

3. **Add Metrics** (No breaking changes)
   ```python
   from src.utils.metrics import RequestTimer, get_metrics_collector
   
   with RequestTimer() as timer:
       # Your code
       pass
   
   metrics = get_metrics_collector()
   metrics.record_request(...)
   ```

4. **Add Validation** (Requires API updates)
   ```python
   from src.api.models import QueryRequest
   
   # Use Pydantic models for request validation
   query = QueryRequest(**request_dict)
   ```

---

## 🔌 Using Hybrid Search

### Replace Old Search with Hybrid

**Before:**
```python
from src.retrieval.search_engine import retrieve_context

results = retrieve_context(query, top_k=5)
```

**After:**
```python
from src.retrieval.search_engine import get_search_engine

engine = get_search_engine()
results = engine.hybrid_search(
    query, 
    top_k=5,
    semantic_weight=0.7,  # 70% semantic
    keyword_weight=0.3     # 30% keyword
)
```

### Configure Weights

Adjust weights based on your use case:

```python
# For product databases (keyword important)
results = engine.hybrid_search(
    query, 
    semantic_weight=0.5,
    keyword_weight=0.5
)

# For documents (semantic important)
results = engine.hybrid_search(
    query,
    semantic_weight=0.8,
    keyword_weight=0.2
)
```

---

## 💾 Using Cache

### Basic Usage

```python
from src.utils.cache_manager import get_cache_manager

cache = get_cache_manager()

# Check if result is cached
result = cache.get("user_query", filters={"category": "product"})
if result:
    print("Cache hit!")
    return result

# Perform expensive operation
result = run_query()

# Cache the result (default: 1 hour)
cache.set("user_query", result, filters={"category": "product"})
```

### With TTL

```python
# Cache for 30 minutes
cache.set(query, result, ttl_seconds=1800)

# Cache for 1 day
cache.set(query, result, ttl_seconds=86400)
```

### Clear Cache

```python
# Clear specific entry
cache.clear()

# Get stats
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']}")
```

---

## 📊 Using Metrics

### Basic Usage

```python
from src.utils.metrics import get_metrics_collector, RequestMetrics
import time

metrics = get_metrics_collector()

# Track a request
start = time.time()
# ... do work ...
elapsed = (time.time() - start) * 1000

metric = RequestMetrics(
    request_id="req-123",
    endpoint="/query",
    method="POST",
    processing_time_ms=elapsed,
    status_code=200
)
metrics.record_request(metric)

# Get summary
summary = metrics.get_summary()
print(f"Success rate: {summary['success_rate']}")
```

### Using RequestTimer

```python
from src.utils.metrics import RequestTimer

with RequestTimer() as timer:
    # Your code
    result = expensive_operation()

print(f"Took {timer.elapsed_ms}ms")
```

### API Endpoint

```bash
# Get overall metrics
curl http://localhost:8000/metrics

# Get endpoint-specific metrics
curl "http://localhost:8000/metrics?endpoint=/query"
```

---

## 🛡️ Error Handling

### Custom Exceptions

```python
from src.api.error_handlers import (
    FileIngestionError,
    QueryProcessingError,
    QdrantConnectionError
)

try:
    process_file(filepath)
except FileIngestionError as e:
    logger.error(f"Error: {e.message}")
    return {"error_code": e.error_code, "message": e.message}
```

### Creating Custom Errors

```python
from src.api.error_handlers import RAGException

class CustomError(RAGException):
    def __init__(self, details):
        super().__init__(
            message="Something went wrong",
            error_code="CUSTOM_ERROR",
            status_code=400,
            details=details
        )

# Use
raise CustomError({"field": "email", "value": "invalid@"})
```

---

## 📝 Using Validation

### Request Models

```python
from src.api.models import QueryRequest, IngestResponse

# Validate incoming request
try:
    query = QueryRequest(**request_data)
except ValidationError as e:
    return {"errors": e.errors()}

# Create typed response
response = IngestResponse(
    message="Success",
    filename="doc.pdf",
    file_type="pdf",
    chunks_created=45
)

return response.model_dump()
```

### Custom Validation

```python
from pydantic import BaseModel, Field, validator

class CustomRequest(BaseModel):
    email: str = Field(..., regex=r"^[^@]+@[^@]+\.[^@]+$")
    count: int = Field(..., ge=1, le=100)
    
    @validator('email')
    def email_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Email cannot be empty')
        return v
```

---

## 🌍 CORS & Security

### Enable CORS

In `.env`:
```
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,https://myapp.com
```

### Enable API Key Auth

In `.env`:
```
API_KEY_REQUIRED=true
API_KEY=super-secret-key-12345
```

In requests:
```bash
curl -H "X-API-Key: super-secret-key-12345" \
  http://localhost:8000/query
```

---

## 📚 Using New Endpoints

### Single File Ingestion
```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@document.pdf" \
  -F "source=catalog" \
  -F "category=products"
```

### Batch Ingestion
```bash
curl -X POST "http://localhost:8000/batch-ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["file1.pdf", "file2.json"],
    "source": "docs",
    "category": "technical"
  }'
```

### Query with Options
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the options?",
    "top_k": 5,
    "filters": {"category": "product"},
    "use_cache": true
  }'
```

---

## 🔍 Debugging

### View Logs
```bash
# All logs
tail -f logs/app.log

# Errors only
tail -f logs/errors.log

# Real-time
tail -f logs/app.log | grep ERROR
```

### Check Status
```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# Cache stats
curl http://localhost:8000/cache-stats
```

### Set Log Level

In `.env`:
```
LOG_LEVEL=DEBUG    # Verbose
LOG_LEVEL=INFO     # Normal
LOG_LEVEL=WARNING  # Warnings only
```

---

## 🧪 Testing

### Run Tests
```bash
# Install pytest
pip install pytest

# Run all tests
pytest tests/

# Run specific test
pytest tests/test_enhancements.py::test_cache_hit_on_repeated_query -v

# With coverage
pytest tests/ --cov=src
```

---

## 🚀 Deployment

### Using Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Using Gunicorn (Production)
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app
```

---

## ⚙️ Configuration Reference

### Critical Settings
```env
QDRANT_URL=http://localhost:6333              # Required
EMBEDDING_MODEL=nomic-embed-text              # Required
```

### Performance Settings
```env
CACHE_TTL=3600                  # Cache expiry (seconds)
CACHE_MAX_SIZE=1000            # Max cached queries
```

### Security Settings
```env
API_KEY_REQUIRED=false         # Enable API key check
API_KEY=your-secret-key        # Your API key
ALLOWED_ORIGINS=http://localhost:3000  # CORS
```

### Logging Settings
```env
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR
```

---

## 📈 Performance Tips

1. **Use Caching**: Enable `use_cache=true` for repeated queries
2. **Adjust Top-K**: Lower for speed, higher for quality
3. **Batch Process**: Use `/batch-ingest` for multiple files
4. **Monitor Metrics**: Regular check `/metrics` endpoint
5. **Configure TTL**: Set appropriate cache expiry

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Cache not working | Clear: `DELETE /qdrant/clear?confirm=true` |
| Slow queries | Lower `top_k`, check `/metrics` |
| Auth failures | Verify `API_KEY` in `.env` and request header |
| High memory | Reduce `CACHE_MAX_SIZE` |
| No results | Check `/health`, verify documents uploaded |

---

## 📞 Getting Help

1. Check `ENHANCED_README.md` for detailed docs
2. View logs in `logs/` directory
3. Check metrics at `/metrics` endpoint
4. Test with `/health` endpoint
5. Review error codes in `src/api/error_handlers.py`

---

## ✨ What's Next?

- Add custom search filters
- Implement advanced caching strategies
- Set up monitoring dashboards
- Add rate limiting
- Create admin panel

---

**Status**: Ready for Integration ✅  
**Last Updated**: November 12, 2025
