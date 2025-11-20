"""
Configuration module for Hybrid RAG Application.
Enhanced with comprehensive settings management.
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    app_name: str = "Hybrid RAG AI Assistant"
    version: str = "2.0.0"
    environment: str = os.getenv("ENVIRONMENT", "development")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", 8000))
    debug: bool = environment == "development"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Security
    api_key_required: bool = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
    api_key: Optional[str] = os.getenv("API_KEY", None)
    allowed_origins: List[str] = (
        os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
    )
    
    # Qdrant
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    qdrant_collection_name: str = os.getenv("QDRANT_COLLECTION_NAME", "hybrid_docs")
    
    # Embeddings
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    
    # LLM
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    
    # Cache
    cache_ttl: int = int(os.getenv("CACHE_TTL", 3600))
    cache_max_size: int = int(os.getenv("CACHE_MAX_SIZE", 1000))
    redis_url: Optional[str] = os.getenv("REDIS_URL", None)
    
    # File Upload
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE", 100))
    upload_dir: str = os.getenv("UPLOAD_DIR", "data/sample_docs")
    
    # HuggingFace
    huggingface_api_key: Optional[str] = os.getenv("HUGGINGFACE_API_KEY", None)
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export
settings = get_settings()
