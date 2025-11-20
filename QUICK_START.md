"""
Quick Reference Guide for Enhanced Hybrid RAG Application
"""

# ==================== QUICK START ====================

## 1️⃣ Setup (2 minutes)
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Start Ollama
ollama pull nomic-embed-text
ollama serve

# Run app
python -m uvicorn src.main:app --reload
```

## 2️⃣ Test the API (1 minute)
```bash
# Health check
curl http://localhost:8000/health

# Upload a document
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@sample.pdf"

# Query
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the options?"}'

# Check metrics
curl http://localhost:8000/metrics
```

# ==================== KEY FEATURES QUICK REFERENCE ====================

## 🔍 Hybrid Search
- Combines semantic (vector) + keyword matching
- Weights: 70% semantic, 30% keyword
- In: `src/retrieval/search_engine.py`

## 💾 Caching
- Default TTL: 1 hour (3600 seconds)
- Max cache size: 1000 entries
- File: `src/utils/cache_manager.py`

## 📊 Metrics
- Real-time tracking of all requests
- Cache hit rates, processing times
- File: `src/utils/metrics.py`
- Endpoint: `GET /metrics`

## 🛡️ Error Handling
- Custom exceptions for all error types
- Structured error responses
- File: `src/api/error_handlers.py`

## 📝 Validation
- Pydantic models for all requests/responses
- Type-safe data handling
- File: `src/api/models.py`

## 🔐 Security
- Optional API key authentication
- CORS configuration
- File: `src/main.py`

## 📋 Logging
- Structured logging to file + console
- Separate error log
- Files: `logs/app.log`, `logs/errors.log`

# ==================== FILE STRUCTURE ====================

```
src/
├── main.py                      # FastAPI app setup
├── api/
│   ├── models.py               # ✨ NEW: Pydantic schemas
│   ├── routes.py               # ✨ NEW: All endpoints
│   └── error_handlers.py        # ✨ NEW: Error handling
├── retrieval/
│   └── search_engine.py         # ✨ ENHANCED: Hybrid search
├── config/
│   └── settings_enhanced.py     # ✨ NEW: Advanced settings
└── utils/
    ├── logger.py               # ✨ ENHANCED: Structured logging
    ├── cache_manager.py         # ✨ NEW: Caching system
    └── metrics.py              # ✨ NEW: Metrics tracking

✨ = NEW or SIGNIFICANTLY ENHANCED
```

# ==================== API ENDPOINTS SUMMARY ====================

### Health & Info
- GET  /                      Info & features
- GET  /health                Health check
- GET  /metrics               Performance metrics
- GET  /cache-stats           Cache statistics

### Document Management
- POST   /ingest              Upload single file
- POST   /batch-ingest        Upload multiple files
- DELETE /qdrant/clear        Clear vector database

### Query
- POST /query                 Natural language query

# ==================== CONFIGURATION ====================

### Required Environment Variables
```
QDRANT_URL=http://localhost:6333
EMBEDDING_MODEL=nomic-embed-text
```

### Optional Environment Variables
```
API_KEY_REQUIRED=false        # Enable API key check
API_KEY=secret-key            # Your API key
CACHE_TTL=3600               # Cache expiry (seconds)
CACHE_MAX_SIZE=1000          # Max cached queries
LOG_LEVEL=INFO               # Logging level
```

# ==================== COMMON TASKS ====================

### Clear Cache
```python
from src.utils.cache_manager import get_cache_manager
get_cache_manager().clear()
```

### Get Cache Stats
```python
from src.utils.cache_manager import get_cache_manager
stats = get_cache_manager().get_stats()
print(stats)
```

### Get Metrics
```python
from src.utils.metrics import get_metrics_collector
summary = get_metrics_collector().get_summary()
print(summary)
```

### Enable API Key Auth
1. Set in .env: `API_KEY_REQUIRED=true`
2. Use header: `X-API-Key: your-api-key`

### View Logs
```bash
tail -f logs/app.log          # All logs
tail -f logs/errors.log       # Errors only
```

# ==================== PERFORMANCE TIPS ====================

1. **Caching**: Use cached results for repeated queries (enabled by default)
2. **Batch Ingestion**: Upload multiple documents at once
3. **Top-K Tuning**: Lower top_k for faster searches, higher for better quality
4. **Hybrid Search**: Default 70/30 weights work well for most cases
5. **Logging**: Set LOG_LEVEL=WARNING in production to reduce I/O

# ==================== TROUBLESHOOTING ====================

### Query returns empty results
1. Check documents uploaded: POST /ingest
2. Verify Qdrant connection: GET /health
3. Check logs: tail -f logs/errors.log

### Cache not working
1. Clear cache: DELETE /qdrant/clear?confirm=true
2. Check stats: GET /cache-stats
3. Verify TTL setting

### Slow performance
1. Check metrics: GET /metrics
2. Reduce top_k in queries
3. Enable caching with use_cache=true

### Authentication errors
1. Check API_KEY_REQUIRED in .env
2. Include X-API-Key header in requests
3. Verify API key matches

# ==================== NEXT STEPS ====================

1. Read ENHANCED_README.md for detailed documentation
2. Explore /docs endpoint for interactive API documentation
3. Check logs in `logs/` directory
4. Run GET /metrics to see system performance
5. Customize in config/settings_enhanced.py as needed

Happy Coding! 🚀
