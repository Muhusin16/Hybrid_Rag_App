from qdrant_client import QdrantClient

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "hybrid_docs"

client = QdrantClient(url=QDRANT_URL)

points, _ = client.scroll(
    collection_name=COLLECTION_NAME,
    with_payload=True,
    limit=100
)

print(f"🔍 Found {len(points)} points in '{COLLECTION_NAME}' collection\n")
for idx, p in enumerate(points, start=1):
    payload = p.payload
    print(f"--- POINT #{idx} ---")
    print(f"Metadata: {payload.get('metadata', payload)}")
    print(f"Content: {payload.get('page_content', payload.get('text', ''))[:200]}...")
    print()
