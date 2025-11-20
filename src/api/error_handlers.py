"""
Error handling and custom exceptions for the RAG application.
"""

from fastapi import HTTPException, status
from typing import Optional, Dict, Any
from datetime import datetime
import traceback
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RAGException(Exception):
    """Base exception for RAG application."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "RAG_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for response."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class FileIngestionError(RAGException):
    """Raised when file ingestion fails."""
    
    def __init__(self, filename: str, reason: str, details: Optional[Dict] = None):
        message = f"Failed to ingest file '{filename}': {reason}"
        super().__init__(
            message=message,
            error_code="FILE_INGESTION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details or {"filename": filename, "reason": reason}
        )


class UnsupportedFileTypeError(RAGException):
    """Raised when file type is not supported."""
    
    def __init__(self, filename: str, file_type: str):
        message = f"File type '{file_type}' is not supported"
        super().__init__(
            message=message,
            error_code="UNSUPPORTED_FILE_TYPE",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"filename": filename, "file_type": file_type}
        )


class QueryProcessingError(RAGException):
    """Raised when query processing fails."""
    
    def __init__(self, query: str, reason: str, details: Optional[Dict] = None):
        message = f"Failed to process query: {reason}"
        super().__init__(
            message=message,
            error_code="QUERY_PROCESSING_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details or {"query": query, "reason": reason}
        )


class QdrantConnectionError(RAGException):
    """Raised when connection to Qdrant fails."""
    
    def __init__(self, reason: str):
        message = f"Failed to connect to Qdrant: {reason}"
        super().__init__(
            message=message,
            error_code="QDRANT_CONNECTION_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"reason": reason}
        )


class EmbeddingError(RAGException):
    """Raised when embedding generation fails."""
    
    def __init__(self, reason: str, details: Optional[Dict] = None):
        message = f"Embedding generation failed: {reason}"
        super().__init__(
            message=message,
            error_code="EMBEDDING_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details or {"reason": reason}
        )


class LLMError(RAGException):
    """Raised when LLM processing fails."""
    
    def __init__(self, reason: str, details: Optional[Dict] = None):
        message = f"LLM processing failed: {reason}"
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details or {"reason": reason}
        )


class ValidationError(RAGException):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, reason: str):
        message = f"Validation error in field '{field}': {reason}"
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"field": field, "reason": reason}
        )


class AuthenticationError(RAGException):
    """Raised when authentication fails."""
    
    def __init__(self, reason: str = "Invalid or missing API key"):
        super().__init__(
            message=reason,
            error_code="AUTHENTICATION_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details={"reason": reason}
        )


class RateLimitError(RAGException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, retry_after: int = 60):
        message = f"Rate limit exceeded. Retry after {retry_after} seconds"
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after}
        )


def handle_exception(exc: Exception) -> Dict[str, Any]:
    """
    Handle and log exceptions.
    Returns a standardized error response.
    """
    if isinstance(exc, RAGException):
        logger.error(
            f"{exc.error_code}: {exc.message}",
            extra={"error_code": exc.error_code, "details": exc.details}
        )
        return exc.to_dict()
    else:
        # Unknown exception
        error_code = "INTERNAL_ERROR"
        message = "An unexpected error occurred"
        logger.error(
            message,
            exc_info=True,
            extra={"traceback": traceback.format_exc()}
        )
        return {
            "error_code": error_code,
            "message": message,
            "details": {"type": type(exc).__name__},
            "timestamp": datetime.utcnow().isoformat()
        }


def create_http_exception(exc: RAGException) -> HTTPException:
    """Convert RAGException to FastAPI HTTPException."""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.to_dict()
    )
