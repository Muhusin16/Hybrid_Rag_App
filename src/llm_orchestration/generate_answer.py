# from langchain_ollama import OllamaLLM
# from langchain_core.prompts import PromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from langchain_core.runnables import RunnableSequence
# import json

# def generate_final_answer(context: str, query: str) -> dict:
#     """
#     Generate a clean, structured JSON answer from the retrieved context.
#     The LLM is explicitly instructed to respond in JSON format for easy parsing.
#     """
#     template = """
#     You are a structured data assistant that helps extract configuration information
#     about signboard materials such as Cast Metal, Bronze, Aluminum, etc.

#     The following CONTEXT contains structured data describing finishes, fonts,
#     mounting options, and other attributes of these materials.

#     Your task:
#     - Understand the QUERY
#     - Extract or summarize relevant structured information
#     - Always respond **only** in valid JSON format (no markdown, no text outside JSON)

#     ---
#     CONTEXT:
#     {context}
#     ---
#     QUERY:
#     {query}
#     ---

#     Output format (strict JSON):
#     {{
#         "material": "<Material Name>",
#         "finishes": ["<Finish 1>", "<Finish 2>", ...],
#         "styles": ["<Style 1>", "<Style 2>", ...],
#         "fonts": ["<Font 1>", "<Font 2>", ...],
#         "mounting": ["<Mount 1>", "<Mount 2>", ...],
#         "logo_options": ["<Option 1>", "<Option 2>", ...]
#     }}

#     Notes:
#     - If a category (like styles or logo_options) has no info, return it as an empty array.
#     - If the material name is unknown, try to infer it from the context.
#     - Do not include any explanations, text, or commentary — only JSON.
#     """

#     prompt = PromptTemplate(template=template, input_variables=["context", "query"])
#     llm = OllamaLLM(model="llama3")  # You can switch to "llama3" or "phi3" for better consistency
#     chain = RunnableSequence(prompt | llm | StrOutputParser())

#     try:
#         response = chain.invoke({"context": context, "query": query})

#         # Try to parse as JSON
#         try:
#             parsed = json.loads(response)
#         except json.JSONDecodeError:
#             # Attempt to fix if LLM added stray text
#             cleaned = response.strip().split("```json")[-1].split("```")[0].strip()
#             try:
#                 parsed = json.loads(cleaned)
#             except Exception:
#                 parsed = {"raw_answer": response}

#         # Ensure all expected keys exist
#         for key in ["material", "finishes", "styles", "fonts", "mounting", "logo_options"]:
#             parsed.setdefault(key, [] if key != "material" else "")

#         return parsed

#     except Exception as e:
#         return {"error": str(e)}


from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence
import json
import re


def generate_final_answer(context: str, query: str) -> dict:
    """
    Generate a clean, structured JSON answer for the given query and context.
    - Uses LLM for reasoning and structure
    - Adds rule-based fallback if model misses data
    - Ensures all values are safe and consistently formatted
    """

    template = """
    You are a structured data assistant for signage materials and configurations.

    CONTEXT:
    {context}

    USER QUERY:
    {query}

    TASK:
    Based only on the context, respond strictly in JSON format with these fields:
    {{
      "material": "<material name>",
      "finishes": ["<Finish 1>", "<Finish 2>", ...],
      "styles": ["<Style 1>", "<Style 2>", ...],
      "fonts": ["<Font 1>", "<Font 2>", ...],
      "mounting": ["<Mount 1>", "<Mount 2>", ...],
      "logo_options": ["<Logo Option 1>", "<Logo Option 2>", ...]
    }}

    RULES:
    - Only include data directly found in the CONTEXT.
    - If no info exists for a field, return an empty list.
    - Never add comments, notes, or explanations.
    - Always return valid JSON only.
    """

    prompt = PromptTemplate(template=template, input_variables=["context", "query"])
    llm = OllamaLLM(model="tinyllama")  # Switch to 'llama3' for stronger reasoning
    chain = RunnableSequence(prompt | llm | StrOutputParser())

    try:
        # 🔹 Step 1: Invoke model
        response = chain.invoke({"context": context, "query": query}).strip()

        # 🔹 Step 2: Try parsing JSON safely
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            cleaned = response[json_start:json_end]
            try:
                result = json.loads(cleaned)
            except Exception:
                result = {}

        # 🔹 Step 3: Ensure every key exists and is safe
        for key in ["material", "finishes", "styles", "fonts", "mounting", "logo_options"]:
            if key not in result:
                result[key] = [] if key != "material" else ""

        # 🔹 Step 4: Normalize values safely (avoid .strip() errors)
        for key in ["finishes", "styles", "fonts", "mounting", "logo_options"]:
            value = result.get(key, [])
            cleaned_list = []
            if isinstance(value, list):
                for v in value:
                    # handle nested lists
                    if isinstance(v, list):
                        cleaned_list.extend(
                            [str(x).strip().title() for x in v if str(x).strip()]
                        )
                    elif isinstance(v, (str, int, float)):
                        cleaned_list.append(str(v).strip().title())
            elif isinstance(value, str):
                cleaned_list.append(value.strip().title())
            result[key] = sorted(set(cleaned_list))

        # 🔹 Step 5: Fallbacks (regex-based extraction if model missed it)
        if not result.get("finishes") and "Available finishes for" in context:
            match = re.search(r"Available finishes for .*?: (.+)", context)
            if match:
                result["finishes"] = [f.strip().title() for f in match.group(1).split(",")]

        if not result.get("mounting") and "Mounting options for" in context:
            match = re.search(r"Mounting options for .*?: (.+)", context)
            if match:
                result["mounting"] = [f.strip().title() for f in match.group(1).split(",")]

        if not result.get("fonts") and "Font:" in context:
            fonts = re.findall(r"Font:\s*([\w\s\(\)\-\']+)", context)
            if fonts:
                result["fonts"] = sorted(set([f.strip().title() for f in fonts]))

        if not result.get("material"):
            match = re.search(r"Material available:\s*(.*)", context)
            if match:
                result["material"] = match.group(1).strip()

        # 🔹 Step 6: Return clean final schema
        return {
            "material": result.get("material", ""),
            "finishes": result.get("finishes", []),
            "styles": result.get("styles", []),
            "fonts": result.get("fonts", []),
            "mounting": result.get("mounting", []),
            "logo_options": result.get("logo_options", []),
        }

    except Exception as e:
        return {
            "material": "",
            "finishes": [],
            "styles": [],
            "fonts": [],
            "mounting": [],
            "logo_options": [],
            "error": str(e),
        }
