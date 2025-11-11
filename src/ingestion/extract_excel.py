# src/ingestion/extract_excel.py
import pandas as pd
from langchain_core.documents import Document
from pathlib import Path

def extract_text_from_excel(file_path: str):
    """
    Extract rows from Excel or CSV as plain text Documents.
    Each row becomes a small text block for embedding.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError("Unsupported file type. Use .xlsx, .xls, or .csv")

    # Convert each row to readable text
    docs = []
    for idx, row in df.iterrows():   # ✅ add idx here
        text = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": str(path.name),
                    "row_number": idx   # ✅ now idx is defined
                },
            )
        )


    print(f"✅ Extracted {len(docs)} records from {file_path}")
    return docs
