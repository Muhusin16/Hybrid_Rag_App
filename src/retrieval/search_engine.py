"""
Enhanced search engine with hybrid retrieval (semantic + keyword).
"""

import os
import re
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from langchain_community.embeddings import OllamaEmbeddings
from dotenv import load_dotenv
from src.utils.logger import get_logger
from src.api.error_handlers import QdrantConnectionError, EmbeddingError

logger = get_logger(__name__)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "hybrid_docs")


class HybridSearchEngine:
    """Hybrid search engine combining semantic and keyword-based retrieval."""
    
    def __init__(self, 
                 qdrant_url: str = QDRANT_URL,
                 qdrant_api_key: Optional[str] = QDRANT_API_KEY,
                 embedding_model: str = EMBEDDING_MODEL,
                 collection_name: str = COLLECTION_NAME):
        """Initialize the search engine."""
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        
        self.client: Optional[QdrantClient] = None
        self.embedder: Optional[OllamaEmbeddings] = None
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize Qdrant client and embeddings."""
        try:
            self.client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
            self.embedder = OllamaEmbeddings(model=self.embedding_model)
            logger.info("Search engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize search engine: {e}")
            raise QdrantConnectionError(str(e))
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text.
        Simple approach: split and filter common words.
        """
        # Convert to lowercase and split
        words = text.lower().split()
        
        # Remove common stop words and short words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'must', 'can', 'what', 'which', 'who', 'when', 'where',
            'why', 'how', 'as', 'if', 'from', 'with', 'by', 'that', 'this', 'it'
        }
        
        keywords = [
            word for word in words
            if len(word) > 2 and word not in stop_words and word.isalnum()
        ]
        
        return list(set(keywords))  # Deduplicate
    
    def _semantic_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Semantic search using vector embeddings.
        
        Args:
            query: Query text
            top_k: Number of results to retrieve
        
        Returns:
            List of documents with scores
        """
        try:
            logger.debug(f"Performing semantic search for: {query[:50]}...")
            
            # Generate query embedding
            query_vector = self.embedder.embed_query(query)
            
            # Search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
            )
            
            # Parse results
            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append({
                    "text": payload.get("page_content") or payload.get("text") or "",
                    "metadata": payload,
                    "score": hit.score,
                    "search_type": "semantic"
                })
            
            logger.debug(f"Semantic search returned {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise EmbeddingError(str(e))
    
    def _keyword_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Keyword-based search using text matching.
        
        Args:
            query: Query text
            top_k: Number of results to retrieve
        
        Returns:
            List of documents with relevance scores
        """
        try:
            logger.debug(f"Performing keyword search for: {query[:50]}...")
            
            keywords = self._extract_keywords(query)
            if not keywords:
                logger.warning("No keywords extracted from query")
                return []
            
            # Build filter conditions for keywords
            keyword_filters = []
            for keyword in keywords[:5]:  # Limit to 5 keywords
                keyword_filters.append(
                    qmodels.FieldCondition(
                        key="page_content",
                        match=qmodels.MatchText(text=keyword)
                    )
                )
            
            # Scroll through collection with keyword filter
            hits, _ = self.client.scroll(
                collection_name=self.collection_name,
                with_payload=True,
                limit=top_k * 2,  # Get more candidates
                scroll_filter=qmodels.Filter(
                    should=keyword_filters  # Match any keyword
                ) if keyword_filters else None
            )
            
            # Score results by keyword frequency
            results = []
            for hit in hits:
                payload = hit.payload or {}
                text = payload.get("page_content") or payload.get("text") or ""
                
                # Calculate keyword match score
                keyword_count = sum(
                    len(re.findall(rf'\b{kw}\b', text, re.IGNORECASE))
                    for kw in keywords
                )
                
                # Normalize score to 0-1 range
                score = min(keyword_count / (len(keywords) + 1), 1.0)
                
                results.append({
                    "text": text,
                    "metadata": payload,
                    "score": score,
                    "search_type": "keyword",
                    "matched_keywords": [kw for kw in keywords if re.search(rf'\b{kw}\b', text, re.IGNORECASE)]
                })
            
            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]
            
            logger.debug(f"Keyword search returned {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []
    
    def hybrid_search(self, query: str, top_k: int = 5, 
                     semantic_weight: float = 0.7, 
                     keyword_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword-based retrieval.
        
        Args:
            query: Query text
            top_k: Number of final results
            semantic_weight: Weight for semantic search results (0-1)
            keyword_weight: Weight for keyword search results (0-1)
        
        Returns:
            Merged and ranked results
        """
        logger.info(f"Hybrid search for: {query[:50]}...")
        
        # Perform both searches
        semantic_results = self._semantic_search(query, top_k=top_k * 2)
        keyword_results = self._keyword_search(query, top_k=top_k * 2)
        
        # Create a merged result dict with combined scores
        merged: Dict[str, Dict[str, Any]] = {}
        
        # Add semantic results
        for result in semantic_results:
            text_hash = hash(result["text"])
            merged[text_hash] = {
                **result,
                "final_score": result["score"] * semantic_weight
            }
        
        # Add/merge keyword results
        for result in keyword_results:
            text_hash = hash(result["text"])
            if text_hash in merged:
                # Merge scores
                merged[text_hash]["final_score"] += result["score"] * keyword_weight
                merged[text_hash]["search_type"] = "hybrid"
            else:
                result["final_score"] = result["score"] * keyword_weight
                merged[text_hash] = result
        
        # Sort by final score and return top_k
        final_results = sorted(
            merged.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )[:top_k]
        
        logger.info(f"Hybrid search returned {len(final_results)} results")
        return final_results
    
    def retrieve_context(self, query: str, top_k: int = 5, 
                        use_hybrid: bool = True) -> List[Dict[str, Any]]:
        """
        Main retrieval method.
        
        Args:
            query: User query
            top_k: Number of documents to retrieve
            use_hybrid: Whether to use hybrid search
        
        Returns:
            List of retrieved documents
        """
        if use_hybrid:
            return self.hybrid_search(query, top_k=top_k)
        else:
            return self._semantic_search(query, top_k=top_k)

    # -------------------------
    # Helpers: direct Qdrant lookups for structured data
    # -------------------------
    def get_finishes_for_material(self, material: Optional[str] = None, limit: int = 200) -> List[str]:
        """
        Query Qdrant for documents of type 'finish' for a given material.
        Returns a deduplicated sorted list of finish names.
        """
        try:
            if not self.client:
                self._initialize()
            # build filter: must include type == finish and optionally material match
            must = [qmodels.FieldCondition(key="type", match=qmodels.MatchValue(value="finish"))]
            if material:
                must.append(qmodels.FieldCondition(key="material", match=qmodels.MatchValue(value=material)))

            hits, _ = self.client.scroll(
                collection_name=self.collection_name,
                with_payload=True,
                limit=limit,
                scroll_filter=qmodels.Filter(must=must)
            )
            found = []
            for hit in hits:
                payload = hit.payload or {}
                name = payload.get("finish_name") or payload.get("name") or payload.get("value")
                if not name:
                    txt = payload.get("page_content") or payload.get("text") or ""
                    m = re.search(r"Finish option for .*?:\s*(.+)", txt)
                    if m:
                        name = m.group(1).strip()
                if name:
                    found.append(name)
            # dedupe preserving order
            return list(dict.fromkeys(found))
        except Exception as e:
            logger.debug(f"get_finishes_for_material failed: {e}")
            return []

    def get_font_heights(self, font_name: str, material: Optional[str] = None, limit: int = 200) -> List[str]:
        """
        Query Qdrant for documents of type 'font_size' matching a font name.
        Returns a sorted list of height strings (deduplicated).
        """
        try:
            if not self.client:
                self._initialize()
            # build must conditions: type == font_size and font_name matches
            must = [qmodels.FieldCondition(key="type", match=qmodels.MatchValue(value="font_size"))]
            must.append(qmodels.FieldCondition(key="font_name", match=qmodels.MatchValue(value=font_name)))
            if material:
                must.append(qmodels.FieldCondition(key="material", match=qmodels.MatchValue(value=material)))

            hits, _ = self.client.scroll(
                collection_name=self.collection_name,
                with_payload=True,
                limit=limit,
                scroll_filter=qmodels.Filter(must=must)
            )
            heights = []
            for hit in hits:
                payload = hit.payload or {}
                h = payload.get("height") or payload.get("value")
                if h:
                    heights.append(str(h))
                else:
                    txt = payload.get("page_content") or payload.get("text") or ""
                    m = re.search(r"Height:\s*([0-9A-Za-z\/\- ]+)", txt)
                    if m:
                        heights.append(m.group(1).strip())
            heights = list(dict.fromkeys(heights))  # dedupe, preserve order
            # Sort numerically if all are numbers, else as strings
            try:
                heights = sorted(heights, key=lambda x: int(x) if str(x).isdigit() else x)
            except Exception:
                heights = sorted(heights)
            return heights
        except Exception as e:
            logger.debug(f"get_font_heights failed: {e}")
            return []


# Global search engine instance
_search_engine: Optional[HybridSearchEngine] = None


def get_search_engine() -> HybridSearchEngine:
    """Get the global search engine instance."""
    global _search_engine
    if _search_engine is None:
        _search_engine = HybridSearchEngine()
    return _search_engine


def retrieve_context(query: str, top_k: int = 5, use_hybrid: bool = True) -> List[Dict[str, Any]]:
    """
    Retrieve context for a query.
    
    Args:
        query: Query text
        top_k: Number of results to retrieve
        use_hybrid: Whether to use hybrid search
    
    Returns:
        List of retrieved documents
    """
    engine = get_search_engine()
    return engine.retrieve_context(query, top_k=top_k, use_hybrid=use_hybrid)
