# src/ingestion/ingest_cast_metal.py
import json
from pathlib import Path
import os
from typing import Dict, List, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance
from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "hybrid_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


def ingest_cast_metal_json(file_path: str) -> Dict[str, Any]:
    """
    Ingests cast-metal.json into Qdrant with structured embedding texts.
    Each option (font, heights, depths, profiles, mounting) becomes its own document.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    material = data.get("name", "Cast Metal")

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    # Material root
    texts.append(f"Material: {material}. Cast metal letters product.")
    metadatas.append({"type": "material", "material": material, "source": path.name})

    # Mounting options (if present)
    repeater = data.get("letters", {}).get("repeater", {}).get("controlsGroup", [])
    for group in repeater:
        for ctrl in group.get("controls", []):
            # Many JSONs might use different keys; check variations
            key = ctrl.get("key", "").lower()
            name_key = ctrl.get("name", "")
            if "mount" in key or "mount" in name_key.lower():
                for opt in ctrl.get("options", []):
                    mount_name = opt.get("name")
                    if mount_name:
                        texts.append(f"Mounting option for {material}: {mount_name}")
                        metadatas.append({
                            "type": "mounting",
                            "material": material,
                            "mounting_name": mount_name,
                            "source": path.name
                        })

            # Finishes / color selectors (material-dependent color selectors)
            # Look for controls that represent a color/finish selector and attempt to extract options
            for group in repeater:
                for ctrl in group.get("controls", []):
                    key = ctrl.get("key", "")
                    ctrl_type = ctrl.get("type", "").lower()
                    material_dependent = bool(ctrl.get("materialDependent", False))
                    # detect color/finish selectors
                    if ctrl_type == "color" or "finish" in key.lower() or "color" in key.lower():
                        options = ctrl.get("options", []) or []
                        if options:
                            for opt in options:
                                name = opt.get("name") or opt.get("value")
                                if name:
                                    texts.append(f"Finish option for {material}: {name}")
                                    metadatas.append({
                                        "type": "finish",
                                        "material": material,
                                        "finish_name": name,
                                        "source": path.name
                                    })
                        else:
                            # No explicit options: mark as a material-dependent selector so downstream
                            # logic can handle it (e.g., fetch from separate palette or UI mapping)
                            texts.append(f"Finish selector for {material}: material-dependent color selector")
                            metadatas.append({
                                "type": "finish_selector",
                                "material": material,
                                "selector_key": key,
                                "material_dependent": material_dependent,
                                "source": path.name
                            })

    # Fonts, heights, depths, profiles
    for group in data.get("letters", {}).get("fonts", []):
        group_name = group.get("name", "")
        for font in group.get("options", []):
            font_name = font.get("name")
            if not font_name:
                continue
            lowercase = font.get("lowercase", True)
            profiles = font.get("profiles", []) or []

            # Font root doc
            texts.append(f"Font option: {font_name} | Group: {group_name} | Lowercase: {lowercase} | Profiles: {', '.join(profiles) if profiles else 'none'}")
            metadatas.append({
                "type": "font",
                "material": material,
                "font_name": font_name,
                "group": group_name,
                "lowercase": lowercase,
                "profiles": profiles,
                "source": path.name
            })

            # Heights + depths
            for h in font.get("heights", []):
                height = h.get("height")
                depth = h.get("depth")
                lowercase_override = h.get("lowercase")
                text = f"Font: {font_name} | Height: {height} | Depth: {depth} | LowercaseAllowed: {lowercase_override if lowercase_override is not None else lowercase}"
                texts.append(text)
                metadatas.append({
                    "type": "font_size",
                    "material": material,
                    "font_name": font_name,
                    "height": height,
                    "depth": depth,
                    "lowercase": lowercase_override if lowercase_override is not None else lowercase,
                    "source": path.name
                })

    # Modifiers
    modifiers = data.get("letters", {}).get("modifiers", {}) or {}
    for k, v in modifiers.items():
        texts.append(f"Pricing modifier: {k} = {v}")
        metadatas.append({
            "type": "modifier",
            "modifier_key": k,
            "modifier_value": v,
            "material": material,
            "source": path.name
        })

    # -------------------------
    # 5. FINISHES (materials -> colorsFinishes)
    # -------------------------
    for mat in data.get("materials", []) or []:
        mat_name = mat.get("name") or mat.get("material")
        if not mat_name:
            continue
        for cf_group in (mat.get("colorsFinishes") or []):
            # each group may contain options
            for opt in (cf_group.get("options") or []):
                # option could be a dict or string
                if isinstance(opt, dict):
                    finish_name = opt.get("name") or opt.get("value") or str(opt)
                else:
                    finish_name = str(opt)
                if finish_name:
                    texts.append(f"Finish option for {mat_name}: {finish_name}")
                    metadatas.append({
                        "type": "finish",
                        "material": mat_name,
                        "finish_name": finish_name,
                        "source": path.name
                    })

    # Save to Qdrant
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )

    embedder = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME, embedding=embedder)

    vectorstore.add_texts(texts=texts, metadatas=metadatas)

    return {"count": len(texts), "material": material}
