import os
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "hybrid_docs")

def retrieve_context(query: str, top_k: int = 5):
    """
    Retrieve the most semantically similar chunks from Qdrant.
    Returns top_k documents (with text + metadata).
    """
    # 1️⃣ Initialize Qdrant and embeddings
    print("🔍 Connecting to Qdrant for retrieval...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    embedder = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    # 2️⃣ Convert query to vector
    print("🔢 Generating embedding for query...")
    query_vector = embedder.embed_query(query)

    # 3️⃣ Search Qdrant
    print(f"📚 Searching for top {top_k} similar chunks...")
    search_results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
    )

    # 4️⃣ Parse results
    contexts = []
    for r in search_results:
        payload = r.payload or {}
        content = payload.get("content") or payload.get("text") or payload.get("page_content", "")
        metadata = payload
        contexts.append({
            "text": content,
            "metadata": metadata,
            "score": r.score
        })

    print(f"✅ Retrieved {len(contexts)} similar chunks for query.")
    return contexts
