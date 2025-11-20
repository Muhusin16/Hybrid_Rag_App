"""
Hybrid RAG Application Main Entry Point
Enhanced with:
- Modular API structure
- Comprehensive error handling
- Request/response validation
- Caching and monitoring
- Security features (CORS, rate limiting, API keys)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Import router
from src.api.routes import router
from src.api.error_handlers import RAGException, handle_exception
from src.utils.logger import get_logger

logger = get_logger(__name__)
load_dotenv()

# Get configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# ==================== LIFESPAN & STARTUP ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    # Startup
    logger.info("🚀 Hybrid RAG Application starting up...")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Hybrid RAG Application shutting down...")


# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Hybrid RAG AI Assistant",
    version="2.0.0",
    description="Enhanced RAG system with hybrid search, caching, monitoring, and security",
    lifespan=lifespan
)


# ==================== MIDDLEWARE ====================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted Host Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"]
)


# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(RAGException)
async def rag_exception_handler(request, exc: RAGException):
    """Handle RAG exceptions."""
    logger.error(f"RAG Exception: {exc.message}", extra={"error_code": exc.error_code})
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle all other exceptions."""
    error_dict = handle_exception(exc)
    return JSONResponse(
        status_code=500,
        content=error_dict
    )


# ==================== INCLUDE ROUTES ====================

app.include_router(router)


# ==================== MAIN ENTRY POINT ====================


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=ENVIRONMENT == "development"
    )
