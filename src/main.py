# src/main.py

from fastapi import FastAPI, UploadFile, Form, HTTPException, Query
import shutil
from pathlib import Path
from dotenv import load_dotenv
from src.ingestion.extract_text import extract_text_from_pdf
from src.ingestion.chunk_text import chunk_documents
from src.ingestion.embed_store import store_in_qdrant
from src.llm_orchestration.generate_answer import generate_final_answer
from src.postprocessing.citation_formatter import format_with_citations
from src.config import settings

# ✅ New imports for Qdrant + Ollama embeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import os
import re

app = FastAPI(title="Hybrid RAG AI Assistant (Ollama Local)")

load_dotenv()

# --- Constants ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = "hybrid_docs"

# ------------------------------
# 📥 FILE INGESTION ENDPOINT
# ------------------------------
@app.post("/ingest")
async def ingest_file(file: UploadFile):
    """Handles dynamic ingestion of PDFs, Excel, CSV, or JSON product files."""
    upload_path = Path(f"data/sample_docs/{file.filename}")
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ext = upload_path.suffix.lower()
    if ext == ".pdf":
        docs = extract_text_from_pdf(upload_path)
        chunks = chunk_documents(docs)
        store_in_qdrant(chunks)

    elif ext in [".xlsx", ".xls", ".csv"]:
        from src.ingestion.extract_excel import extract_text_from_excel
        docs = extract_text_from_excel(upload_path)
        chunks = chunk_documents(docs)
        store_in_qdrant(chunks)

    elif ext == ".json":
        from src.ingestion.ingest_json_dynamic import ingest_json_dynamic
        ingest_json_dynamic(upload_path)
        return {"message": f"{file.filename} ingested successfully (JSON structured data)!"}

    else:
        return {"error": "Unsupported file type"}

    return {"message": f"{file.filename} ingested successfully!"}


# ------------------------------
# 🧠 QUERY (RAG) ENDPOINT
# ------------------------------
@app.post("/query")
async def query_dynamic(user_query: str = Form(...)):
    """
    Smarter query handler:
    - Handles multiple materials (e.g., "cast and bronze metal")
    - Handles multiple categories (e.g., "finishes and mounting options")
    - Uses direct metadata filtering for accuracy
    """
    import re

    try:
        # 🧠 Setup
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        embedder = OllamaEmbeddings(model="nomic-embed-text")
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embedder,
        )

        query_lower = user_query.lower()

        # 🔍 Material detection
        material_patterns = [
            ("cast metal", "Cast Metal"),
            ("bronze", "Bronze"),
            ("aluminum", "Aluminum"),
            ("brass", "Brass"),
            ("steel", "Steel"),
            ("sublimated metal", "Sublimated Metal"),
            ("flat cut metal", "Flat Cut Metal"),
        ]

        materials_found = []
        for key, pretty in material_patterns:
            if re.search(rf"\b{key}\b", query_lower):
                materials_found.append(pretty)

        if not materials_found and "cast" in query_lower and "metal" in query_lower:
            materials_found = ["Cast Metal"]

        if not materials_found:
            materials_found = ["Cast Metal"]

        # 🧩 Category detection
        categories_map = {
            "finish": ["finish", "color", "paint"],
            "font": ["font", "typeface"],
            "mounting": ["mount", "install"],
            "modifier": ["price", "cost", "rate", "modifier"]
        }

        categories_found = []
        for cat, keywords in categories_map.items():
            if any(k in query_lower for k in keywords):
                categories_found.append(cat)

        if not categories_found:
            categories_found = list(categories_map.keys())

        # 🧩 Process each material
        answers = []
        for mat in materials_found:
            combined_result = {
                "material": mat,
                "finishes": [],
                "styles": [],
                "fonts": [],
                "mounting": [],
                "logo_options": []
            }

            for cat in categories_found:
                # 🧠 Metadata filter search (not just similarity)
                hits, _ = client.scroll(
                    collection_name=COLLECTION_NAME,
                    with_payload=True,
                    limit=100,
                    scroll_filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="metadata.metal",
                                match=qmodels.MatchValue(value=mat)
                            ),
                            qmodels.FieldCondition(
                                key="metadata.category",
                                match=qmodels.MatchValue(value=cat)
                            )
                        ]
                    ),
                )

                if not hits:
                    continue

                # Build the context text from retrieved payloads
                context_chunks = []
                for h in hits:
                    payload = h.payload.get("metadata", h.payload)
                    text = h.payload.get("page_content") or h.payload.get("text") or ""
                    if text:
                        context_chunks.append(text)

                if not context_chunks:
                    continue

                context = "\n".join(context_chunks)
                structured_answer = generate_final_answer(context, user_query)

                for key in ["finishes", "styles", "fonts", "mounting", "logo_options"]:
                    if key in structured_answer and structured_answer[key]:
                        combined_result[key].extend(structured_answer[key])

            # ✅ If no data found, mark it clearly
            has_data = any(combined_result[k] for k in ["finishes", "mounting", "fonts", "styles", "logo_options"])
            if not has_data:
                combined_result["error"] = f"No data found for {mat}."

            answers.append(combined_result)

        return {
            "query": user_query,
            "materials_found": materials_found,
            "categories_found": categories_found,
            "answers": answers
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ------------------------------
# 🧹 QDRANT CLEAR ENDPOINT
# ------------------------------
@app.delete("/qdrant/clear")
async def clear_qdrant_collection(source: str = Query(None, description="Optional: delete by source name")):
    """
    Delete vectors from Qdrant.
    - If 'source' is provided → deletes all points with that metadata source.
    - If not → deletes the entire collection.
    """
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    if source:
        print(f"🧹 Deleting vectors where source = {source}")
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="source",  # ✅ Correct flattened key
                            match=qmodels.MatchValue(value=source)
                        )
                    ]
                )
            ),
        )
        return {"message": f"Deleted all records for source '{source}'."}

    else:
        print(f"💥 Deleting entire collection: {COLLECTION_NAME}")
        client.delete_collection(collection_name=COLLECTION_NAME)
        return {"message": f"Collection '{COLLECTION_NAME}' deleted successfully!"}


# ------------------------------
# 🚀 MAIN ENTRY POINT
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
