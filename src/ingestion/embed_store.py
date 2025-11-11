from langchain_qdrant import QdrantVectorStore
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance
import os

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = "hybrid_docs"

def store_in_qdrant(chunks):
    print("🚀 Connecting to Qdrant...")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Ensure collection exists
    if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
        print(f"📦 Setting up collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )

    print("🔢 Generating embeddings using Ollama...")
    embedder = OllamaEmbeddings(model="nomic-embed-text")

    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]

    # ✅ FIXED: use `embedding` instead of `embeddings`
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embedder,
    )

    vectorstore.add_texts(texts=texts, metadatas=metadatas)

    print("✅ Successfully stored embeddings in Qdrant!")
