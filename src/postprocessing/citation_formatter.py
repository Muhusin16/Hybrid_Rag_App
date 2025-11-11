def format_with_citations(answer: str, context_docs: list) -> str:
    """
    Adds source references (citations) to the generated answer.
    Supports both dict and LangChain Document objects.
    """
    if not context_docs:
        return answer

    sources = []
    for doc in context_docs:
        # Handle both dict and Document object types
        if hasattr(doc, "metadata"):  
            meta = doc.metadata or {}
        elif isinstance(doc, dict):  
            meta = doc.get("metadata", {})
        else:
            meta = {}

        source_name = meta.get("source", "Unknown")
        page_no = meta.get("page_number") or meta.get("row_number")

        source_entry = f"{source_name}"
        if page_no:
            source_entry += f" (page {page_no})"

        if source_entry not in sources:
            sources.append(source_entry)

    citation_text = "\n\n📚 **Sources:**\n" + "\n".join([f"- {src}" for src in sources])
    return f"{answer.strip()}\n\n---{citation_text}"
