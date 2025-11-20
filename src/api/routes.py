# src/api/routes.py
"""
API Routes for the Hybrid RAG Application.
All endpoints organized and documented.
"""

from fastapi import APIRouter, UploadFile, Form, HTTPException, Query, Depends, Header
from typing import Optional, Dict, Any, List
import shutil
from pathlib import Path
import time
import uuid
from datetime import datetime

# Import models
from src.api.models import (
    IngestResponse, BatchIngestRequest, BatchIngestResponse,
    QueryRequest, QueryResponse, RetrievedDocument, StructuredAnswer,
    MaterialAnswer, FontsAnswer, FontAttributeAnswer,
    MountingAnswer, FinishesAnswer, ModifiersAnswer,
    GeneralStructuredAnswer,
    QdrantClearRequest, QdrantClearResponse,
    HealthResponse, APIInfoResponse
)

# Import error handlers
from src.api.error_handlers import (
    RAGException, FileIngestionError, UnsupportedFileTypeError,
    QueryProcessingError, QdrantConnectionError, AuthenticationError,
    RateLimitError, handle_exception, create_http_exception
)

# Import utilities
from src.utils.logger import get_logger
from src.utils.cache_manager import get_cache_manager
from src.utils.metrics import (
    get_metrics_collector, RequestMetrics, RequestTimer
)

# Import services
from src.ingestion.extract_text import extract_text_from_pdf
from src.ingestion.chunk_text import chunk_documents
from src.ingestion.embed_store import store_in_qdrant
from src.llm_orchestration.generate_answer import generate_final_answer
from src.retrieval.search_engine import get_search_engine
from src.postprocessing.citation_formatter import format_with_citations
from src.llm_orchestration.cast_metal_answer import answer_cast_metal_query
from src.config import settings

# Qdrant imports
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import os
from dotenv import load_dotenv
import re

logger = get_logger(__name__)
load_dotenv()

# Initialize router
router = APIRouter()

# Constants
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = "hybrid_docs"
SUPPORTED_FILE_TYPES = {".pdf", ".xlsx", ".xls", ".csv", ".json"}


# ==================== DEPENDENCY: API KEY VALIDATION ====================

def validate_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    api_key_required = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
    expected_api_key = os.getenv("API_KEY", None)

    if api_key_required and expected_api_key:
        if not x_api_key or x_api_key != expected_api_key:
            logger.warning(f"Invalid API key attempt")
            raise AuthenticationError("Invalid or missing API key")

    return x_api_key or "anonymous"


# ==================== HEALTH & INFO ENDPOINTS ====================

@router.get("/", response_model=APIInfoResponse, tags=["Info"])
async def root():
    return APIInfoResponse(
        app_name="Hybrid RAG AI Assistant (Enhanced)",
        version="2.0.0",
        docs_url="http://localhost:8000/docs",
        endpoints={
            "ingest": "POST /ingest - Single file ingestion",
            "batch_ingest": "POST /batch-ingest - Batch file ingestion",
            "query": "POST /query - RAG query with hybrid search",
            "health": "GET /health - Health check",
            "metrics": "GET /metrics - Performance metrics",
            "qdrant_clear": "DELETE /qdrant/clear - Clear vectors",
        },
        features=[
            "Hybrid Search (Semantic + Keyword)",
            "Response Caching",
            "Rate Limiting",
            "API Key Authentication",
            "Request Monitoring",
            "Pydantic Validation",
            "Comprehensive Error Handling",
            "Structured Logging"
        ]
    )


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        qdrant_connected = bool(client.get_collections())
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        qdrant_connected = False

    return HealthResponse(
        status="healthy" if qdrant_connected else "degraded",
        message="All systems operational" if qdrant_connected else "Some services unavailable",
        version="2.0.0",
        qdrant_connected=qdrant_connected,
        embedding_model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
    )


# ==================== INGEST ENDPOINTS ====================

@router.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_file(
    file: UploadFile,
    api_key: str = Depends(validate_api_key)
):
    """
    Handles single file ingestion for PDFs, Excel, CSV, or JSON files.
    Extracts content, chunks documents, generates embeddings, and stores in Qdrant.
    """
    request_id = str(uuid.uuid4())
    
    try:
        logger.info(f"[{request_id}] Ingesting file: {file.filename}")
        
        # Validate file type
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_FILE_TYPES:
            raise UnsupportedFileTypeError(
                file.filename,
                f"Supported types: {', '.join(SUPPORTED_FILE_TYPES)}"
            )
        
        # Save uploaded file
        upload_dir = Path("data/sample_docs")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"[{request_id}] File saved to {file_path}")
        
        # Extract content based on file type
        docs = []
        if file_ext == ".pdf":
            docs = extract_text_from_pdf(str(file_path))
        elif file_ext in [".xlsx", ".xls", ".csv"]:
            from src.ingestion.extract_excel import extract_text_from_excel
            docs = extract_text_from_excel(str(file_path))
        elif file_ext == ".json":
            from src.ingestion.ingest_json_dynamic import ingest_cast_metal_json
            result = ingest_cast_metal_json(str(file_path))
            logger.info(f"[{request_id}] JSON file ingested successfully: {result}")
            return IngestResponse(
                message=f"{file.filename} ingested successfully (JSON structured data)!",
                filename=file.filename,
                file_type=file_ext,
                chunks_created=result.get("count") if isinstance(result, dict) else None,
                timestamp=datetime.utcnow()
            )
        
        if not docs:
            raise FileIngestionError(
                file.filename,
                "No content could be extracted from the file"
            )
        
        # Chunk documents
        logger.info(f"[{request_id}] Chunking {len(docs)} documents")
        chunks = chunk_documents(docs)
        
        # Store in Qdrant
        logger.info(f"[{request_id}] Storing {len(chunks)} chunks in Qdrant")
        store_in_qdrant(chunks)
        
        logger.info(f"[{request_id}] File ingestion completed successfully")
        
        # Record metrics
        metrics = RequestMetrics(
            request_id=request_id,
            endpoint="/ingest",
            method="POST",
            processing_time_ms=0,
            status_code=200,
            response_size_bytes=0
        )
        get_metrics_collector().record_request(metrics)
        
        return IngestResponse(
            message=f"{file.filename} ingested successfully!",
            filename=file.filename,
            file_type=file_ext,
            chunks_created=len(chunks),
            vector_count=len(chunks),
            timestamp=datetime.utcnow()
        )
    
    except UnsupportedFileTypeError as e:
        logger.error(f"[{request_id}] Unsupported file type: {e.message}")
        raise create_http_exception(e)
    
    except FileIngestionError as e:
        logger.error(f"[{request_id}] File ingestion error: {e.message}")
        raise create_http_exception(e)
    
    except RAGException as e:
        logger.error(f"[{request_id}] RAG Exception: {e.message}")
        raise create_http_exception(e)
    
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File ingestion failed: {str(e)}")


@router.post("/batch-ingest", response_model=BatchIngestResponse, tags=["Ingestion"])
async def batch_ingest(
    request: BatchIngestRequest,
    api_key: str = Depends(validate_api_key)
):
    """
    Handles batch ingestion of multiple files.
    Processes each file and returns results for all files.
    """
    request_id = str(uuid.uuid4())
    
    logger.info(f"[{request_id}] Batch ingesting {len(request.files)} files")
    
    results = []
    successful = 0
    failed = 0
    
    for file_path in request.files:
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_ext = path.suffix.lower()
            if file_ext not in SUPPORTED_FILE_TYPES:
                raise UnsupportedFileTypeError(
                    path.name,
                    f"Supported types: {', '.join(SUPPORTED_FILE_TYPES)}"
                )
            
            logger.info(f"[{request_id}] Processing: {path.name}")
            
            # Extract content
            docs = []
            if file_ext == ".pdf":
                docs = extract_text_from_pdf(str(path))
            elif file_ext in [".xlsx", ".xls", ".csv"]:
                from src.ingestion.extract_excel import extract_text_from_excel
                docs = extract_text_from_excel(str(path))
            elif file_ext == ".json":
                from src.ingestion.ingest_json_dynamic import ingest_cast_metal_json
                try:
                    result = ingest_cast_metal_json(str(path))
                    results.append(IngestResponse(
                        message=f"{path.name} ingested successfully",
                        filename=path.name,
                        file_type=file_ext,
                        chunks_created=result.get("count") if isinstance(result, dict) else None,
                        timestamp=datetime.utcnow()
                    ))
                    successful += 1
                    continue
                except Exception as e:
                    logger.error(f"[{request_id}] Error ingesting JSON {path.name}: {e}")
                    results.append(IngestResponse(
                        message=f"Failed to ingest {path.name}",
                        filename=path.name,
                        file_type=file_ext,
                        error=str(e),
                        timestamp=datetime.utcnow()
                    ))
                    failed += 1
                    continue
            
            if docs:
                chunks = chunk_documents(docs)
                store_in_qdrant(chunks)
                results.append(IngestResponse(
                    message=f"{path.name} ingested successfully",
                    filename=path.name,
                    file_type=file_ext,
                    chunks_created=len(chunks),
                    vector_count=len(chunks),
                    timestamp=datetime.utcnow()
                ))
                successful += 1
            else:
                results.append(IngestResponse(
                    message=f"No content extracted from {path.name}",
                    filename=path.name,
                    file_type=file_ext,
                    error="No extractable content",
                    timestamp=datetime.utcnow()
                ))
                failed += 1
        
        except Exception as e:
            logger.error(f"[{request_id}] Error processing {file_path}: {str(e)}")
            results.append(IngestResponse(
                message=f"Failed to ingest {Path(file_path).name}",
                filename=Path(file_path).name,
                file_type=Path(file_path).suffix.lower(),
                error=str(e),
                timestamp=datetime.utcnow()
            ))
            failed += 1
    
    logger.info(f"[{request_id}] Batch ingestion completed: {successful} successful, {failed} failed")
    
    return BatchIngestResponse(
        total_files=len(request.files),
        successful=successful,
        failed=failed,
        results=results
    )

def detect_intent(query: str, structured_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return an intent dict: {"intent": "<one of material/fonts/font_attribute/mounting/finishes/modifiers/general>", "target_font": Optional[str], "attribute": Optional[str]}
    Uses a simple, deterministic set of rules. This is intentionally conservative to avoid mis-classifying.
    """
    q = query.lower()

    # material intent
    if re.search(r"\bmaterials?\b|\bwhich materials\b|\bwhat materials\b", q):
        return {"intent": "material", "target_font": None, "attribute": None}

    # fonts (explicit)
    if re.search(r"\bfonts?\b|\btypefaces?\b|\blist fonts\b|\bavailable fonts\b", q) and not re.search(r"height|depth|profile|profile\b|size|sizes|heights|depths", q):
        return {"intent": "fonts", "target_font": None, "attribute": None}

    # mounting
    if re.search(r"\bmount(ing)?\b|\binstall\b|\bmount options\b", q):
        return {"intent": "mounting", "target_font": None, "attribute": None}

    # finishes
    if re.search(r"\bfinish(es)?\b|\bcolor(s)?\b|\bpaint\b", q):
        return {"intent": "finishes", "target_font": None, "attribute": None}

    # modifiers / price
    if re.search(r"\bprice\b|\bcost\b|\bmodifier\b|\bpricing\b", q):
        return {"intent": "modifiers", "target_font": None, "attribute": None}

    # font attribute (heights/depths/profiles)
    if re.search(r"\bheight(s)?\b|\bdepth(s)?\b|\bprofile(s)?\b|\bsize(s)?\b", q):
        # try to find font name in query using structured_ctx (fonts list) or capitalized tokens
        fonts = [f.get("name") for f in structured_ctx.get("fonts", []) if isinstance(f, dict) and f.get("name")]
        # attempt exact match of any known font in the query (case-insensitive)
        target = None
        for font in fonts:
            if font and re.search(rf"\b{re.escape(font.lower())}\b", q):
                target = font
                break
        if not target:
            # fallback: capture quoted or capitalized single-word token after 'for' or 'of'
            m = re.search(r"(?:for|of)\s+\"?([A-Za-z0-9 &\-\']{2,40})\"?", query)
            if m:
                candidate = m.group(1).strip()
                target = candidate
        return {"intent": "font_attribute", "target_font": target, "attribute": None}

    # default -> general structured answer
    return {"intent": "general", "target_font": None, "attribute": None}


def extract_sources_from_docs(docs: List[Dict[str, Any]]) -> List[str]:
    srcs = []
    for d in docs:
        meta = d.get("metadata", {}) if isinstance(d, dict) else {}
        # support nested payload structure
        if isinstance(meta, dict):
            # Sometimes payload contains nested 'metadata' and 'page_content'
            if "source" in meta:
                s = meta.get("source")
            elif isinstance(meta.get("metadata"), dict) and "source" in meta.get("metadata"):
                s = meta.get("metadata").get("source")
            else:
                s = None
            if s and s not in srcs:
                srcs.append(s)
    return srcs

    # -------------------------
# API key dependency
# -------------------------
def validate_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    api_key_required = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
    expected_api_key = os.getenv("API_KEY", None)
    if api_key_required and expected_api_key:
        if not x_api_key or x_api_key != expected_api_key:
            logger.warning("Invalid API key attempt")
            raise AuthenticationError("Invalid or missing API key")
    return x_api_key or "anonymous"

# ==================== QUERY ENDPOINT ====================

@router.post("/query", response_model=Dict[str, Any], tags=["Query"])
async def query_endpoint(request: QueryRequest, api_key: str = Depends(validate_api_key)):
    """
    Single /query endpoint that auto-detects intent and returns the appropriate specialized answer.
    Request body expected to match QueryRequest shape:
    {
      "query": "...",
      "top_k": 5,
      "filters": { ... },
      "use_cache": true
    }
    """
    request_id = str(uuid.uuid4())
    start = time.time()

    # Basic validation (use pydantic model fields)
    user_query = getattr(request, "query", "")
    top_k = int(getattr(request, "top_k", 5))
    filters = getattr(request, "filters", None)
    use_cache = bool(getattr(request, "use_cache", True))

    if not user_query or not user_query.strip():
        raise HTTPException(status_code=400, detail="Query text is required")

    with RequestTimer() as timer:
        try:
            logger.info(f"[{request_id}] Query received: {user_query[:120]}")

            # cache check
            cache_manager = get_cache_manager()
            cache_key = user_query
            if use_cache:
                cached = cache_manager.get(cache_key, filters)
                if cached:
                    logger.info(f"[{request_id}] Cache hit")
                    cached["cache_hit"] = True
                    cached["processing_time_ms"] = timer.elapsed_ms
                    return cached

            # retrieval (hybrid)
            search_engine = get_search_engine()
            retrieved_docs = search_engine.hybrid_search(user_query, top_k=top_k)

            # Normalize docs for downstream
            docs_normalized = []
            for d in retrieved_docs:
                docs_normalized.append({
                    "text": d.get("text") or d.get("page_content") or "",
                    "metadata": d.get("metadata") or {},
                    "score": d.get("final_score", d.get("score", 0.0)),
                })

            # build doc objects for response (limit top 3 preview)
            retrieved_preview = []
            for d in docs_normalized[:3]:
                retrieved_preview.append({
                    "text": d["text"],
                    "metadata": d["metadata"],
                    "score": d["score"],
                    "source": (d["metadata"].get("source") or d["metadata"].get("metadata", {}).get("source") if isinstance(d["metadata"], dict) else None) or "unknown"
                })

            # Build context to pass to Cast Metal extractor / generic LLM
            combined_context = "\n".join([d["text"] for d in docs_normalized])

            # Run Cast Metal specialized extractor to get strict structured options (fonts, mounting, etc.)
            try:
                cast_struct = answer_cast_metal_query(user_query, combined_context)
                if not isinstance(cast_struct, dict):
                    cast_struct = {}
            except Exception as e:
                logger.warning(f"[{request_id}] Cast metal extractor failed: {e}")
                cast_struct = {}

            # Detect materials present in query (simple heuristics)
            q_lower = user_query.lower()
            material_candidates = []
            for keyword, pretty in [
                ("cast metal", "Cast Metal"),
                ("cast-metal", "Cast Metal"),
                ("castmetal", "Cast Metal"),
                ("bronze", "Bronze"),
                ("aluminum", "Aluminum"),
                ("brass", "Brass"),
                ("steel", "Steel")
            ]:
                if re.search(rf"\b{re.escape(keyword)}\b", q_lower):
                    material_candidates.append(pretty)
            if not material_candidates:
                material_candidates = ["Unknown Material"]

            # Intent detection (use extracted structured ctx to help with font name detection)
            intent_info = detect_intent(user_query, cast_struct or {})

            # sources
            sources = extract_sources_from_docs(docs_normalized)

            # Prepare response based on intent
            intent = intent_info["intent"]
            response_payload: Dict[str, Any] = {}

            # ---------- MATERIALS ----------
            if intent == "material":
                response_payload = MaterialAnswer(
                    query=user_query,
                    materials=material_candidates,
                    sources=sources
                ).dict()

            # ---------- FONTS ----------
            elif intent == "fonts":
                # try to gather fonts from cast_struct (fonts => list of dicts with "name")
                fonts_list = []
                for f in (cast_struct.get("fonts", []) or []):
                    if isinstance(f, dict) and f.get("name"):
                        fonts_list.append(f.get("name"))
                    elif isinstance(f, str):
                        fonts_list.append(f)
                # dedupe
                fonts_list = list(dict.fromkeys([f for f in fonts_list if f]))
                response_payload = FontsAnswer(
                    query=user_query,
                    material=material_candidates[0] if material_candidates else None,
                    fonts=fonts_list,
                    sources=sources
                ).dict()

            # ---------- FONT ATTRIBUTE ----------
            elif intent == "font_attribute":
                target_font = intent_info.get("target_font")
                # Attempt to resolve target_font from cast_struct if not found directly
                if not target_font:
                    fonts = cast_struct.get("fonts", []) or []
                    if fonts:
                        # pick first font as fallback
                        first = fonts[0]
                        target_font = first.get("name") if isinstance(first, dict) else first

                # determine which attribute user asked about
                attr = None
                if re.search(r"\bheight(s)?\b|\bsize(s)?\b", q_lower):
                    attr = "heights"
                elif re.search(r"\bdepth(s)?\b", q_lower):
                    attr = "depths"
                elif re.search(r"\bprofile(s)?\b", q_lower):
                    attr = "profiles"
                else:
                    # fallback: return heights by default
                    attr = "heights"

                values = []
                # find in cast_struct fonts list
                for f in (cast_struct.get("fonts", []) or []):
                    if isinstance(f, dict) and f.get("name") and target_font and f.get("name").lower() == str(target_font).lower():
                        values = f.get(attr, []) or []
                        break

                # Fallback: if no values found in cast_struct, query Qdrant for font_size docs
                # For font heights, always query Qdrant to get the complete list (not limited by top_k)
                if not values and target_font:
                    try:
                        search_engine = get_search_engine()
                        values = search_engine.get_font_heights(target_font, None) or []
                    except Exception as e:
                        logger.debug(f"[{request_id}] font heights lookup failed: {e}")

                response_payload = FontAttributeAnswer(
                    query=user_query,
                    material=material_candidates[0] if material_candidates else None,
                    font_name=target_font or "",
                    attribute=attr,
                    values=values,
                    sources=sources
                ).dict()

            # ---------- MOUNTING ----------
            elif intent == "mounting":
                mounting_options = cast_struct.get("mounting", []) or []
                response_payload = MountingAnswer(
                    query=user_query,
                    material=material_candidates[0] if material_candidates else None,
                    mounting_options=mounting_options,
                    sources=sources
                ).dict()

            # ---------- FINISHES ----------
            elif intent == "finishes":
                # finishes may come from generic LLM if present in context or cast_struct
                finishes = cast_struct.get("finishes", []) or []
                if not finishes:
                    # Fallback: try generic LLM
                    try:
                        generic = generate_final_answer(combined_context, user_query)
                        finishes = generic.get("finishes", []) or []
                    except Exception:
                        finishes = []

                    # If still empty, ask the search engine for finish docs
                    if not finishes:
                        try:
                            search_engine = get_search_engine()
                            material_name = material_candidates[0] if material_candidates else None
                            # If the query mentions the product 'Cast Metal' (not a specific sub-material),
                            # retrieve finishes across all materials in the collection
                            if material_name and material_name.lower() in ("cast metal", "cast-metal", "castmetal", "unknown material"):
                                finishes = search_engine.get_finishes_for_material(None) or []
                            elif material_name:
                                finishes = search_engine.get_finishes_for_material(material_name) or []
                        except Exception as e:
                            logger.debug(f"[{request_id}] finish lookup failed: {e}")
                response_payload = FinishesAnswer(
                    query=user_query,
                    material=material_candidates[0] if material_candidates else None,
                    finishes=finishes,
                    sources=sources
                ).dict()

            # ---------- MODIFIERS ----------
            elif intent == "modifiers":
                modifiers = cast_struct.get("modifiers", {}) or {}
                if not modifiers:
                    try:
                        generic = generate_final_answer(combined_context, user_query)
                        modifiers = generic.get("modifiers", {}) or {}
                    except Exception:
                        modifiers = {}
                response_payload = ModifiersAnswer(
                    query=user_query,
                    material=material_candidates[0] if material_candidates else None,
                    modifiers=modifiers,
                    sources=sources
                ).dict()

            # ---------- GENERAL ----------
            else:
                # Build a comprehensive structured answer using the Cast Metal extractor + fallback to generic LLM
                fonts_out: List[Dict[str, Any]] = []
                for f in cast_struct.get("fonts", []) or []:
                    if isinstance(f, dict):
                        fonts_out.append({
                            "name": f.get("name"),
                            "heights": f.get("heights", []),
                            "depths": f.get("depths", []),
                            "profiles": f.get("profiles", [])
                        })

                mounting_out = cast_struct.get("mounting", []) or []

                # fallback to generic LLM to fill any missing fields
                try:
                    generic = generate_final_answer(combined_context, user_query)
                    finishes_out = generic.get("finishes", []) or []
                    modifiers_out = generic.get("modifiers", {}) or {}
                except Exception:
                    finishes_out = []
                    modifiers_out = {}

                response_payload = GeneralStructuredAnswer(
                    query=user_query,
                    material=material_candidates[0] if material_candidates else None,
                    fonts=[f for f in fonts_out],
                    mounting=mounting_out,
                    finishes=finishes_out,
                    modifiers=modifiers_out,
                    sources=sources
                ).dict()

            # Attach retrieved_docs preview and processing info to the output for transparency
            response_payload["_retrieved_preview"] = retrieved_preview
            response_payload["_processing_time_ms"] = timer.elapsed_ms
            response_payload["_cache_hit"] = False

            # Cache the response
            cache_manager.set(user_query, response_payload, filters, ttl_seconds=1800)

            # record metrics
            metrics = RequestMetrics(
                request_id=request_id,
                endpoint="/query",
                method="POST",
                processing_time_ms=timer.elapsed_ms,
                status_code=200,
                user_query=user_query,
                response_size_bytes=len(str(response_payload).encode("utf-8")),
                cache_hit=False
            )
            get_metrics_collector().record_request(metrics)

            return response_payload

        except RAGException as e:
            logger.error(f"[{request_id}] RAG Exception: {e.message}")
            raise create_http_exception(e)

        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        

        # -------------------------
# Qdrant management endpoints (unchanged)
# -------------------------
@router.delete("/qdrant/clear", response_model=Dict[str, Any], tags=["Management"])
async def clear_qdrant_collection(source: Optional[str] = Query(None), confirm: bool = Query(False), api_key: str = Depends(validate_api_key)):
    request_id = str(uuid.uuid4())
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation required. Set confirm=true to proceed.")
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        if source:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=qmodels.FilterSelector(filter=qmodels.Filter(must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value=source))]))
            )
            return {"message": f"Deleted records for source {source}", "collection": COLLECTION_NAME, "source": source}
        else:
            client.delete_collection(collection_name=COLLECTION_NAME)
            return {"message": f"Collection {COLLECTION_NAME} deleted", "collection": COLLECTION_NAME}
    except Exception as e:
        logger.error(f"Failed to clear Qdrant: {e}")
        raise HTTPException(status_code=500, detail=str(e))
