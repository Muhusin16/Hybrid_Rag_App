import fitz  # PyMuPDF
from langchain_core.documents import Document
from pathlib import Path

def extract_text_from_pdf(file_path: str):
    """
    Extract text from PDF and return as list of LangChain Document objects.
    Each page = one document.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    docs = []
    with fitz.open(file_path) as pdf:
        for page_num, page in enumerate(pdf, start=1):
            text = page.get_text("text")
            if text.strip():
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": str(path.name),
                            "page_number": page_num
                        }
                    )
                )
    print(f"✅ Extracted {len(docs)} pages from {file_path}")
    return docs
