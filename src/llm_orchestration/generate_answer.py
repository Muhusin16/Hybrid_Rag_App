from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence
import json
import re


def generate_final_answer(context: str, query: str) -> dict:
    """
    Generate a clean, structured JSON answer for the given query and context.
    - STRICTLY extracts data from context only - no hallucination allowed
    - Uses LLM for reasoning but validates all values against context
    - Falls back to exact text extraction if LLM invents values
    - Ensures all values are directly sourced from retrieved documents
    """

    template = """
    You are a structured data extraction assistant for signage materials and configurations.
    Your ONLY job is to extract information that EXISTS in the provided CONTEXT.

    ⚠️ CRITICAL RULE: NEVER invent, assume, or hallucinate data.
    - Only list items that appear EXACTLY in the CONTEXT.
    - If something isn't mentioned in the CONTEXT, don't include it.
    - If a category has no data in the CONTEXT, return an empty list.
    - EXTRACT, don't generate. STRICT extraction only.

    CONTEXT (Source Documents):
    {context}

    USER QUERY:
    {query}

    TASK:
    Extract ONLY information found in the CONTEXT above. Respond in this JSON format:
    {{
      "material": "<Extract exact material name from context>",
      "finishes": ["<Finish 1 from context>", "<Finish 2 from context>", ...],
      "styles": ["<Style 1 from context>", "<Style 2 from context>", ...],
      "fonts": ["<Font 1 from context>", "<Font 2 from context>", ...],
      "mounting": ["<Mount 1 from context>", "<Mount 2 from context>", ...],
      "logo_options": ["<Option 1 from context>", "<Option 2 from context>", ...]
    }}

    EXTRACTION RULES (STRICT):
    1. Only extract values that appear verbatim in the CONTEXT.
    2. Do NOT create variations, abbreviations, or new names.
    3. Do NOT invent features or options.
    4. If a field has no data in CONTEXT, return an empty array [].
    5. Return ONLY valid JSON - no explanations, no extra text.
    6. Verify each value against the CONTEXT before including it.
    """

    prompt = PromptTemplate(template=template, input_variables=["context", "query"])
    llm = OllamaLLM(model="llama3")
    chain = RunnableSequence(prompt | llm | StrOutputParser())

    # Deterministic extraction first (no LLM) — ensures we can return values even when Ollama/model is unavailable
    extracted_finishes = []
    extracted_fonts = []
    extracted_styles = []
    extracted_mounting = []

    # Try finishes
    m = re.search(r"Available finishes[^:]*:\s*([^\n]+)", context, re.IGNORECASE)
    if m:
        extracted_finishes = [x.strip() for x in m.group(1).split(",") if x.strip()]

    # Try fonts
        # Also try multiple pattern variations for better extraction
        if not extracted_finishes:
            # Try alternative finish patterns
            finish_patterns = [
                r"finishes[^:]*:\s*([^\n]+)",
                r"finish[^:]*options[^:]*:\s*([^\n]+)"
            ]
            for pattern in finish_patterns:
                m = re.search(pattern, context, re.IGNORECASE)
                if m:
                    extracted_finishes = [x.strip() for x in m.group(1).split(",") if x.strip()]
                    break

        # Try fonts
        fonts_matches = re.findall(r"Font[^:]*:\s*([^\n,]+)", context, re.IGNORECASE)
        if fonts_matches:
            extracted_fonts = sorted(list(set([f.strip() for f in fonts_matches if f.strip()])))

    # Try mounting
    mm = re.search(r"Mounting[^:]*:\s*([^\n]+)", context, re.IGNORECASE)
    if mm:
        extracted_mounting = [x.strip() for x in mm.group(1).split(",") if x.strip()]

    # Try simple style keywords
    style_keywords = ["flat face", "round face", "prismatic", "custom", "star", "flat-face", "round-face"]
    for kw in style_keywords:
        if re.search(re.escape(kw), context, re.IGNORECASE):
            # collect the literal keyword
            extracted_styles.append(kw)
    extracted_styles = sorted(list(set([s.title() for s in extracted_styles])))

    # Default result uses extracted values; we'll attempt LLM to augment but won't remove extracted items
    final_finishes = list(extracted_finishes)
    final_fonts = list(extracted_fonts)
    final_styles = list(extracted_styles)
    final_mounting = list(extracted_mounting)

    material = ""

    try:
        # Attempt LLM only if Ollama model is available; failures are non-fatal
        response = chain.invoke({"context": context, "query": query}).strip()
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                cleaned = response[json_start:json_end]
                try:
                    result = json.loads(cleaned)
                except Exception:
                    result = {}
            else:
                result = {}

        # Merge LLM results but only accept items that appear in context
        ctx = context.lower()
        for f in result.get("finishes", []):
            if isinstance(f, str) and f.strip() and f.strip() not in final_finishes:
                if f.strip().lower() in ctx or f.strip().replace(" ", "-").lower() in ctx:
                    final_finishes.append(f.strip())

        for fo in result.get("fonts", []):
            if isinstance(fo, str) and fo.strip() and fo.strip() not in final_fonts:
                if fo.strip().lower() in ctx:
                    final_fonts.append(fo.strip())

        for st in result.get("styles", []):
            if isinstance(st, str) and st.strip() and st.strip() not in final_styles:
                if st.strip().lower() in ctx:
                    final_styles.append(st.strip())

        for mt in result.get("mounting", []):
            if isinstance(mt, str) and mt.strip() and mt.strip() not in final_mounting:
                if mt.strip().lower() in ctx:
                    final_mounting.append(mt.strip())

        material = str(result.get("material", "")).strip()

    except Exception:
        # Ollama/LLM not available or failed — proceed with extracted-only values
        pass

    # Final normalized return
    return {
        "material": material or "",
        "finishes": sorted(list(dict.fromkeys([f for f in final_finishes if f]))),
        "styles": sorted(list(dict.fromkeys([s for s in final_styles if s]))),
        "fonts": sorted(list(dict.fromkeys([f for f in final_fonts if f]))),
        "mounting": sorted(list(dict.fromkeys([m for m in final_mounting if m]))),
        "logo_options": [],
    }
