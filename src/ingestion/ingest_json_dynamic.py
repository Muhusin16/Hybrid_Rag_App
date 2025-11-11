import json
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "hybrid_docs"

def ingest_json_dynamic(file_path: str):
    """
    Dynamically extracts structured info (fonts, finishes, mounting, pricing, materials)
    from any product JSON config file and stores it in Qdrant.
    Automatically detects finishes/colors at any nested level.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metal_name = data.get("name") or path.stem.replace("-", " ").title()
    print(f"⚙️ Ingesting data for: {metal_name}")

    texts, metadatas = [], []

    # ✅ Always register the material itself
    texts.append(f"Material available: {metal_name}")
    metadatas.append({
        "category": "material",
        "metal": metal_name,
        "source": path.name
    })

    # 🧠 Connect to Qdrant
    client = QdrantClient(url=QDRANT_URL)
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        print(f"📦 Creating collection '{COLLECTION_NAME}'")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )

    embedder = OllamaEmbeddings(model="nomic-embed-text")
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embedder,
    )

    # 🅰 Fonts
    if "letters" in data and "fonts" in data["letters"]:
        for group in data["letters"]["fonts"]:
            for font in group.get("options", []):
                desc = f"Font: {font.get('name')} | Group: {group.get('name')} | Metal: {metal_name}"
                texts.append(desc)
                metadatas.append({
                    "category": "font",
                    "metal": metal_name,
                    "source": path.name
                })

    # 🅱 Finishes (recursive detection for Color/Finish/Paint/Coating)
    finishes = set()

    def extract_finishes(obj):
        """Recursively search for finish/color-related names in nested dicts/lists."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = key.lower()
                # Match any key that hints color/finish
                if any(term in key_lower for term in ["finish", "color", "paint", "coating"]):
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and item.get("name"):
                                finishes.add(item["name"])
                            elif isinstance(item, str):
                                finishes.add(item)
                    elif isinstance(value, dict) and value.get("name"):
                        finishes.add(value["name"])
                # Recurse deeper
                extract_finishes(value)
        elif isinstance(obj, list):
            for i in obj:
                extract_finishes(i)

    # 🔍 Run recursive search
    extract_finishes(data)

    if finishes:
        texts.append(f"Available finishes for {metal_name}: {', '.join(sorted(finishes))}")
        metadatas.append({
            "category": "finish",
            "metal": metal_name,
            "source": path.name
        })

    # 🅲 Mounting options
    mountings = []
    if "letters" in data and "repeater" in data["letters"]:
        for group in data["letters"]["repeater"].get("controlsGroup", []):
            for ctrl in group.get("controls", []):
                if "mount" in ctrl.get("key", "").lower() or "mount" in ctrl.get("name", "").lower():
                    option_names = [opt.get("name") for opt in ctrl.get("options", []) if opt.get("name")]
                    if option_names:
                        mountings.extend(option_names)

    if mountings:
        texts.append(f"Mounting options for {metal_name}: {', '.join(mountings)}")
        metadatas.append({
            "category": "mounting",
            "metal": metal_name,
            "source": path.name
        })

    # 🅳 Modifiers (pricing multipliers etc.)
    if "letters" in data and "modifiers" in data["letters"]:
        mods = data["letters"]["modifiers"]
        desc = " | ".join([f"{k}: {v}" for k, v in mods.items()])
        texts.append(f"Pricing modifiers for {metal_name}: {desc}")
        metadatas.append({
            "category": "modifier",
            "metal": metal_name,
            "source": path.name
        })

    # ✅ Upload all to Qdrant
    if texts:
        vectorstore.add_texts(texts=texts, metadatas=metadatas)
        print(f"✅ Ingested {len(texts)} chunks for {metal_name}")
    else:
        print(f"⚠️ No structured data found in {path.name}")
