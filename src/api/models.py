"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==================== INGESTION MODELS ====================

class FontOption(BaseModel):
    """Font option with nested configuration for cast-metal materials."""
    name: str
    heights: List[str] = Field(default_factory=list)
    depths: List[str] = Field(default_factory=list)
    profiles: List[str] = Field(default_factory=list)


class FileMetadata(BaseModel):
    filename: str
    file_type: str
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: Optional[str] = None
    category: Optional[str] = None


class IngestResponse(BaseModel):
    message: str
    filename: str
    file_type: str
    chunks_created: Optional[int] = None
    vector_count: Optional[int] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchIngestRequest(BaseModel):
    files: List[str]
    source: Optional[str] = None
    category: Optional[str] = None

    @validator("files")
    def files_not_empty(cls, v):
        if not v:
            raise ValueError("At least one file path is required")
        return v


class BatchIngestResponse(BaseModel):
    total_files: int
    successful: int
    failed: int
    results: List[IngestResponse]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ==================== QUERY MODELS ====================

class QueryRequest(BaseModel):
    """Request for RAG query."""
    query: str = Field(..., min_length=1, description="User query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to retrieve")
    filters: Optional[Dict[str, str]] = None
    use_cache: bool = Field(True, description="Whether to use cached results")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the available finishes for cast metal?",
                "top_k": 5,
                "filters": {"material": "Cast Metal"},
                "use_cache": True
            }
        }


class RetrievedDocument(BaseModel):
    text: str
    metadata: Dict[str, Any]
    score: float = Field(..., ge=0.0)
    source: Optional[str] = None


class StructuredAnswer(BaseModel):
    """Structured answer for a material."""
    material: str
    finishes: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    fonts: List[FontOption] = Field(default_factory=list)
    mounting: List[str] = Field(default_factory=list)
    logo_options: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "material": "Cast Metal",
                "finishes": ["Brushed", "Polished"],
                "styles": ["Modern", "Classic"],
                "fonts": [
                    {
                        "name": "Garamond",
                        "heights": ["2", "3"],
                        "depths": ["1/2"],
                        "profiles": ["prismatic"]
                    }
                ],
                "mounting": ["Stud Mount", "Flush Mount"],
                "logo_options": []
            }
        }


class MaterialAnswer(BaseModel):
    query: str
    materials: List[str]
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FontsAnswer(BaseModel):
    query: str
    material: Optional[str]
    fonts: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FontAttributeAnswer(BaseModel):
    query: str
    material: Optional[str]
    font_name: str
    attribute: str  # e.g. "heights" | "depths" | "profiles"
    values: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MountingAnswer(BaseModel):
    query: str
    material: Optional[str]
    mounting_options: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FinishesAnswer(BaseModel):
    query: str
    material: Optional[str]
    finishes: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ModifiersAnswer(BaseModel):
    query: str
    material: Optional[str]
    modifiers: Dict[str, Any] = Field(default_factory=dict)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GeneralStructuredAnswer(BaseModel):
    query: str
    material: Optional[str]
    fonts: List[FontOption] = Field(default_factory=list)
    mounting: List[str] = Field(default_factory=list)
    finishes: List[str] = Field(default_factory=list)
    modifiers: Dict[str, Any] = Field(default_factory=dict)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Legacy / fallback query response (keeps compatibility if needed)
class QueryResponse(BaseModel):
    query: str
    materials_found: List[str]
    categories_found: List[str]
    answers: List[Any] = Field(default_factory=list)
    retrieved_docs: List[RetrievedDocument] = Field(default_factory=list)
    cache_hit: bool = False
    processing_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==================== QDRANT MODELS ====================

class QdrantClearRequest(BaseModel):
    """Request to clear Qdrant collection."""
    source: Optional[str] = Field(None, description="Optional: delete by source name")
    confirm: bool = Field(False, description="Confirmation flag")

    class Config:
        json_schema_extra = {
            "example": {
                "source": None,
                "confirm": True
            }
        }


class QdrantClearResponse(BaseModel):
    """Response from Qdrant clear operation."""
    message: str
    collection_name: str
    deleted_count: Optional[int] = None
    source: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Collection cleared successfully",
                "collection_name": "hybrid_docs",
                "deleted_count": 150,
                "timestamp": "2025-11-12T10:45:00"
            }
        }


# ==================== HEALTH & STATUS MODELS ====================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    message: str
    version: str = "1.0.0"
    qdrant_connected: bool = False
    embedding_model: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "message": "All systems operational",
                "version": "1.0.0",
                "qdrant_connected": True,
                "embedding_model": "nomic-embed-text",
                "timestamp": "2025-11-12T10:50:00"
            }
        }


class APIInfoResponse(BaseModel):
    """API information response."""
    app_name: str
    version: str
    docs_url: str
    endpoints: Dict[str, str]
    features: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "app_name": "Hybrid RAG AI Assistant",
                "version": "1.0.0",
                "docs_url": "http://localhost:8000/docs",
                "endpoints": {
                    "ingest": "POST /ingest - Single file ingestion",
                    "batch_ingest": "POST /batch-ingest - Multiple files"
                },
                "features": ["RAG", "Caching", "Rate Limiting", "Monitoring"]
            }
        }
