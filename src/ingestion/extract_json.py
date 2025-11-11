# src/ingestion/extract_json.py
import json
from pathlib import Path
from langchain_core.documents import Document

def flatten_json(y, prefix=""):
    """Recursively flatten nested JSON into key-value strings."""
    out = {}
    def recurse(t, parent_key=""):
        if isinstance(t, dict):
            for k, v in t.items():
                recurse(v, f"{parent_key}.{k}" if parent_key else k)
        elif isinstance(t, list):
            for i, v in enumerate(t):
                recurse(v, f"{parent_key}[{i}]")
        else:
            out[parent_key] = t
    recurse(y)
    return out

def extract_text_from_json(file_path: str):
    """Extract JSON content into LangChain Document objects."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both dict and list JSON structures
    items = data if isinstance(data, list) else [data]
    docs = []

    for idx, item in enumerate(items):
        flat_item = flatten_json(item)
        text = " | ".join([f"{k}: {v}" for k, v in flat_item.items()])
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": path.name,
                    "record_number": idx + 1
                }
            )
        )

    print(f"✅ Extracted {len(docs)} records from {file_path}")
    return docs
