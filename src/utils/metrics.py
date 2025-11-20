"""
Monitoring and telemetry tracking for RAG application.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
import time
import statistics
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    request_id: str
    endpoint: str
    method: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0
    status_code: int = 200
    user_query: Optional[str] = None
    response_size_bytes: int = 0
    cache_hit: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period."""
    start_time: datetime = field(default_factory=datetime.utcnow)
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_processing_time_ms: float = 0.0
    min_processing_time_ms: float = float('inf')
    max_processing_time_ms: float = 0.0
    total_response_bytes: int = 0
    requests_by_endpoint: Dict[str, int] = field(default_factory=dict)
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        return data


class MetricsCollector:
    """Collects and aggregates request metrics."""
    
    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.
        
        Args:
            retention_hours: How long to keep metrics in memory
        """
        self.retention_hours = retention_hours
        self.requests: List[RequestMetrics] = []
        self.aggregated = AggregatedMetrics()
        self._start_time = time.time()
    
    def record_request(self, metrics: RequestMetrics) -> None:
        """Record a request metric."""
        self.requests.append(metrics)
        self._update_aggregated(metrics)
        
        # Log important metrics
        logger.info(
            f"Request recorded",
            extra={
                "request_id": metrics.request_id,
                "endpoint": metrics.endpoint,
                "processing_time_ms": metrics.processing_time_ms,
                "status_code": metrics.status_code,
                "cache_hit": metrics.cache_hit
            }
        )
        
        # Cleanup old metrics
        self._cleanup_old_metrics()
    
    def _update_aggregated(self, metrics: RequestMetrics) -> None:
        """Update aggregated metrics."""
        self.aggregated.total_requests += 1
        
        if metrics.status_code < 400:
            self.aggregated.successful_requests += 1
        else:
            self.aggregated.failed_requests += 1
        
        if metrics.cache_hit:
            self.aggregated.cache_hits += 1
        else:
            self.aggregated.cache_misses += 1
        
        # Update endpoint counts
        endpoint = metrics.endpoint
        self.aggregated.requests_by_endpoint[endpoint] = \
            self.aggregated.requests_by_endpoint.get(endpoint, 0) + 1
        
        # Update error counts
        if metrics.error:
            error_type = type(metrics.error).__name__ if isinstance(metrics.error, Exception) else str(metrics.error)
            self.aggregated.errors_by_type[error_type] = \
                self.aggregated.errors_by_type.get(error_type, 0) + 1
        
        # Update timing metrics
        processing_times = [r.processing_time_ms for r in self.requests if r.processing_time_ms > 0]
        if processing_times:
            self.aggregated.avg_processing_time_ms = statistics.mean(processing_times)
            self.aggregated.min_processing_time_ms = min(processing_times)
            self.aggregated.max_processing_time_ms = max(processing_times)
        
        # Update response size
        self.aggregated.total_response_bytes += metrics.response_size_bytes
    
    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)
        initial_count = len(self.requests)
        
        self.requests = [
            m for m in self.requests
            if m.timestamp > cutoff_time
        ]
        
        if len(self.requests) < initial_count:
            removed = initial_count - len(self.requests)
            logger.debug(f"Cleaned up {removed} old metric records")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        uptime_seconds = time.time() - self._start_time
        
        return {
            "uptime_seconds": uptime_seconds,
            "total_requests": self.aggregated.total_requests,
            "successful_requests": self.aggregated.successful_requests,
            "failed_requests": self.aggregated.failed_requests,
            "success_rate": (
                f"{(self.aggregated.successful_requests / self.aggregated.total_requests * 100):.2f}%"
                if self.aggregated.total_requests > 0 else "0%"
            ),
            "cache_hit_rate": (
                f"{(self.aggregated.cache_hits / (self.aggregated.cache_hits + self.aggregated.cache_misses) * 100):.2f}%"
                if (self.aggregated.cache_hits + self.aggregated.cache_misses) > 0 else "0%"
            ),
            "avg_processing_time_ms": f"{self.aggregated.avg_processing_time_ms:.2f}",
            "min_processing_time_ms": f"{self.aggregated.min_processing_time_ms:.2f}" if self.aggregated.min_processing_time_ms != float('inf') else "N/A",
            "max_processing_time_ms": f"{self.aggregated.max_processing_time_ms:.2f}",
            "avg_response_size_bytes": (
                f"{self.aggregated.total_response_bytes // self.aggregated.total_requests}"
                if self.aggregated.total_requests > 0 else 0
            ),
            "requests_by_endpoint": self.aggregated.requests_by_endpoint,
            "errors_by_type": self.aggregated.errors_by_type,
            "retention_hours": self.retention_hours
        }
    
    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """Get statistics for a specific endpoint."""
        endpoint_requests = [r for r in self.requests if r.endpoint == endpoint]
        
        if not endpoint_requests:
            return {"message": f"No metrics found for endpoint: {endpoint}"}
        
        processing_times = [r.processing_time_ms for r in endpoint_requests if r.processing_time_ms > 0]
        
        return {
            "endpoint": endpoint,
            "total_requests": len(endpoint_requests),
            "successful": sum(1 for r in endpoint_requests if r.status_code < 400),
            "failed": sum(1 for r in endpoint_requests if r.status_code >= 400),
            "cache_hits": sum(1 for r in endpoint_requests if r.cache_hit),
            "avg_processing_time_ms": f"{statistics.mean(processing_times):.2f}" if processing_times else "N/A",
            "min_processing_time_ms": f"{min(processing_times):.2f}" if processing_times else "N/A",
            "max_processing_time_ms": f"{max(processing_times):.2f}" if processing_times else "N/A",
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.requests.clear()
        self.aggregated = AggregatedMetrics()
        logger.info("Metrics reset")


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector


class RequestTimer:
    """Context manager for timing requests."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.elapsed_ms: float = 0.0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.elapsed_ms = (time.time() - self.start_time) * 1000
