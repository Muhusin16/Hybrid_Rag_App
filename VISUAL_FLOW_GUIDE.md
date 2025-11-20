# VISUAL FLOW CORRECTNESS GUIDE

## Color Legend
- 🟢 **GREEN** = Correct and working
- 🟡 **YELLOW** = Partially working or needs improvement  
- 🔴 **RED** = Broken or missing

---

## 1. INGESTION FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                     FILE INGESTION FLOW                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  User uploads    │
│  PDF/JSON/Excel  │
└────────┬─────────┘
         │
         v
    🔴 RED ZONE 🔴
    ┌──────────────────────────┐
    │  POST /ingest            │
    │  POST /batch-ingest      │
    │  ❌ NOT IMPLEMENTED      │
    │  ❌ NOT IN NEW API       │
    │  ⚠️  Only in old main.py  │
    └──────────────────────────┘
         │ (IF IT WORKED)
         v
    🟢 GREEN ZONE 🟢
    ┌──────────────────────────┐
    │  Parse by type:          │
    │  ✅ PDF → extract_text   │
    │  ✅ JSON → ingest_json   │
    │  ✅ Excel → extract_excel│
    │  ✅ CSV → extract_excel  │
    └──────────────────────────┘
         │
         v
    🟢 GREEN ZONE 🟢
    ┌──────────────────────────┐
    │  Chunk Documents         │
    │  ✅ Correct chunking     │
    │  ✅ Proper overlaps      │
    └──────────────────────────┘
         │
         v
    🟢 GREEN ZONE 🟢
    ┌──────────────────────────┐
    │  Generate Embeddings     │
    │  ✅ Using nomic-embed    │
    │  ✅ 768 dimensions       │
    └──────────────────────────┘
         │
         v
    🟢 GREEN ZONE 🟢
    ┌──────────────────────────┐
    │  Store in Qdrant         │
    │  ✅ Correct metadata     │
    │  ✅ Vector storage       │
    └──────────────────────────┘

STATUS: 🔴 BROKEN (missing endpoint)
```

---

## 2. QUERY FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUERY FLOW                               │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────────┐
    │  User sends query:   │
    │  "What cast metal    │
    │   fonts available?"  │
    └──────────┬───────────┘
               │
               v
          🟢 GREEN 🟢
          ┌──────────────────┐
          │  POST /query ✅  │
          │  Endpoint works  │
          └────────┬─────────┘
                   │
                   v
          🔴 RED ZONE 🔴
          ┌──────────────────────────┐
          │  Query Preprocessing     │
          │  ❌ NOT IMPLEMENTED      │
          │  ❌ EMPTY FILE           │
          │  Uses raw query as-is    │
          └────────┬─────────────────┘
                   │ (SKIPPED)
                   v
          🟢 GREEN 🟢
          ┌──────────────────────────┐
          │  Cache Check             │
          │  ✅ MD5 key generation   │
          │  ✅ TTL management (30m) │
          │  ✅ Hit/miss tracking    │
          └────────┬─────────────────┘
                   │
                   v
          🟢 GREEN 🟢
          ┌──────────────────────────┐
          │  Hybrid Search           │
          │  ✅ Semantic search      │
          │  ✅ Keyword search       │
          │  ✅ Score merging        │
          │  ✅ Result ranking       │
          └────────┬─────────────────┘
                   │
                   v
          🟡 YELLOW 🟡
          ┌──────────────────────────┐
          │  Material Detection      │
          │  ✅ Works                │
          │  ⚠️  Too simplistic      │
          │  ⚠️  Hard-coded list     │
          │  → Detects "Cast Metal"  │
          └────────┬─────────────────┘
                   │
                   v
          🟡 YELLOW 🟡
          ┌──────────────────────────┐
          │  Category Detection      │
          │  ✅ Works                │
          │  ⚠️  Simple matching      │
          │  → Detects "font"        │
          └────────┬─────────────────┘
                   │
                   v
          🟢 GREEN 🟢
          ┌──────────────────────────┐
          │  LLM Processing          │
          │  ✅ Two pipelines        │
          │  ✅ Validation           │
          │  ✅ Error handling       │
          └────────┬─────────────────┘
                   │
      ┌────────────┴─────────────┐
      │                          │
      v                          v
    IS CAST              IS OTHER
    METAL?               MATERIAL?
      │                    │
      v                    v
    🟢 PIPELINE A        🟢 PIPELINE B
    answer_cast_        generate_final
    metal_query()       _answer()
    ✅ Fonts extraction  ✅ Generic extraction
    ✅ Strict validation ✅ Regex + LLM
    ✅ Mounting opts     ✅ Fallback support
      │                    │
      └────────┬───────────┘
               v
         🟢 GREEN 🟢
         ┌──────────────────────────┐
         │  Build StructuredAnswer  │
         │  ✅ Material assigned    │
         │  ✅ Fields populated     │
         │  ✅ Metadata included    │
         └────────┬─────────────────┘
                  │
                  v
         🟡 YELLOW 🟡
         ┌──────────────────────────┐
         │  Format with Citations   │
         │  ✅ Function exists      │
         │  ❌ NOT CALLED           │
         │  Missing in endpoint     │
         └────────┬─────────────────┘
                  │ (SKIPPED)
                  v
         🟢 GREEN 🟢
         ┌──────────────────────────┐
         │  Build Response          │
         │  ✅ QueryResponse model  │
         │  ✅ All fields          │
         │  ✅ Timestamps          │
         └────────┬─────────────────┘
                  │
                  v
         🟢 GREEN 🟢
         ┌──────────────────────────┐
         │  Cache Result            │
         │  ✅ Store in memory      │
         │  ✅ Set TTL              │
         │  ✅ Size management      │
         └────────┬─────────────────┘
                  │
                  v
         🟢 GREEN 🟢
         ┌──────────────────────────┐
         │  Record Metrics          │
         │  ✅ Request logged       │
         │  ✅ Times recorded       │
         │  ✅ Status tracked       │
         └────────┬─────────────────┘
                  │
                  v
         ┌──────────────────────────┐
         │  Return QueryResponse    │
         │  (With all answers)      │
         └──────────────────────────┘

STATUS: 🟢 MOSTLY WORKING (missing citations, no preprocessing)
```

---

## 3. COMPONENT HEALTH CHECK

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPONENT STATUS                             │
└─────────────────────────────────────────────────────────────────┘

API LAYER
├─ routes.py                    🟡 Incomplete (missing /ingest)
├─ models.py                    🟢 Complete
├─ error_handlers.py            🟢 Complete
└─ main.py (legacy)             🟢 Has all endpoints

INGESTION LAYER
├─ extract_text.py             🟢 PDF extraction ✅
├─ extract_excel.py            🟢 Excel/CSV extraction ✅
├─ extract_json.py             🟢 JSON extraction ✅
├─ ingest_json_dynamic.py       🟢 Smart extraction ✅
├─ chunk_text.py               🟢 Chunking ✅
└─ embed_store.py              🟢 Qdrant storage ✅

RETRIEVAL LAYER
├─ search_engine.py            🟢 Hybrid search ✅
└─ query_preprocess.py          🔴 EMPTY ❌

LLM ORCHESTRATION LAYER
├─ generate_answer.py          🟢 Generic pipeline ✅
├─ cast_metal_answer.py        🟢 Cast metal pipeline ✅
├─ prompt_template.py          🟢 Prompts defined ✅
└─ guardrails.py               🟢 Validation ✅

POST-PROCESSING LAYER
├─ citation_formatter.py       🟡 Implemented but not used
├─ confidence_scorer.py        🟢 Available
└─ pii_masking.py              🟢 Available

UTILITIES LAYER
├─ cache_manager.py            🟢 In-memory caching ✅
├─ metrics.py                  🟢 Metrics collection ✅
├─ logger.py                   🟢 Logging ✅
└─ file_utils.py               🟢 File handling ✅

CONFIG LAYER
├─ settings.py                 🟢 Config loaded ✅
└─ constants.py                🟢 Constants defined ✅

EXTERNAL DEPENDENCIES
├─ Qdrant Server               🟢 Connected ✅
├─ Ollama (embeddings)         🟢 nomic-embed-text ✅
└─ Ollama (LLM)                🟢 llama3 / tinyllama ✅

OVERALL: 🟢🟡🔴 = MOSTLY WORKING BUT INCOMPLETE
```

---

## 4. ENDPOINT AVAILABILITY

```
┌─────────────────────────────────────────────────────────────────┐
│                   ENDPOINT STATUS                               │
└─────────────────────────────────────────────────────────────────┘

NEW API (src/api/routes.py)
┌─────────────────────────────────────────────────┐
│ GET /                              🟢 WORKS     │
│ GET /health                        🟢 WORKS     │
│ POST /query                        🟢 WORKS     │
│ POST /ingest                       🔴 MISSING   │
│ POST /batch-ingest                🔴 MISSING   │
│ GET /metrics                       🔴 MISSING   │
│ DELETE /qdrant/clear               🔴 MISSING   │
└─────────────────────────────────────────────────┘

LEGACY API (src/main.py)
┌─────────────────────────────────────────────────┐
│ POST /ingest                       🟢 WORKS     │
│ POST /query                        🟢 WORKS     │
│ DELETE /qdrant/clear               🟢 WORKS     │
└─────────────────────────────────────────────────┘

CURRENT SITUATION:
┌─────────────────────────────────────────────────┐
│ ❌ User accesses new API                        │
│ ❌ Can query but can't upload files             │
│ ❌ Must fall back to legacy API                 │
│ ⚠️  Two separate apps running                  │
└─────────────────────────────────────────────────┘

REQUIRED FIX:
┌─────────────────────────────────────────────────┐
│ ✅ Move ingest endpoints to new API             │
│ ✅ Consolidate into single app                  │
│ ✅ Complete all promised endpoints              │
└─────────────────────────────────────────────────┘
```

---

## 5. CRITICAL PATH ANALYSIS

```
HAPPY PATH (What Works):
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Query   │────▶│ Retrieve │────▶│   LLM    │────▶│ Response │
│ ✅WORKS  │     │ ✅WORKS  │     │ ✅WORKS  │     │ ✅WORKS  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘


BROKEN PATH (File Ingestion):
┌──────────┐     ❌❌❌❌❌
│  Upload  │────▶ ENDPOINT MISSING
│ ❌BROKEN │     ❌❌❌❌❌
└──────────┘


DEGRADED PATH (Query Preprocessing):
┌──────────┐     ┌──────────────┐     ┌──────────┐
│  Query   │────▶│ Preprocess? │────▶│ Search   │
│ "Cast Metal" │ ❌ NOT DONE    │────▶│ "cast..." │
└──────────┘     └──────────────┘     └──────────┘
                                       May miss matches


MISSING FEATURES:
┌──────────┐     ┌──────────┐
│ Response │────▶│ Citations│
│ ✅Ready  │     │ ❌Skipped│
└──────────┘     └──────────┘
```

---

## 6. ISSUE SEVERITY LEVELS

```
🔴 CRITICAL ISSUES (Blocking)
├─ Missing /ingest endpoint
│  └─ Impact: Cannot upload files through new API
└─ Fix Time: 2-3 hours

🟠 MEDIUM ISSUES (Degradation)
├─ Empty query_preprocess.py
│  └─ Impact: Query quality reduced
├─ Case sensitivity issues
│  └─ Impact: Inconsistent results
└─ Fix Time: 1 hour

🟡 LOW ISSUES (Polish)
├─ Citation formatter not integrated
│  └─ Impact: No source attribution
├─ Missing /metrics endpoint
│  └─ Impact: Can't monitor performance
└─ Fix Time: 1.5 hours

TOTAL FIX TIME: 4-5 hours
```

---

## 7. BEFORE vs AFTER

```
BEFORE (Current State)
════════════════════════════════════════════════════════

User Flow:
User ──▶ New API (Query only)     🟢 Works
         ├─ Can query
         └─ Cannot upload files    🔴

File Upload:
User ──▶ Fallback to Legacy API    ⚠️ Two apps
         └─ Must know about it

Data Quality:
Queries ──▶ No preprocessing       🟡 Lower quality
           └─ Typos not handled


AFTER (Fixed State)
════════════════════════════════════════════════════════

User Flow:
User ──▶ New API (Complete)        🟢 All features
         ├─ Can query
         ├─ Can upload files       ✅
         └─ Gets citations         ✅

File Upload:
User ──▶ Single API                🟢 Unified
         └─ Everything in one place

Data Quality:
Queries ──▶ With preprocessing     🟢 Higher quality
           └─ Better matches

Monitoring:
Operations ──▶ Metrics available   🟢 Observable
              └─ Performance tracked
```

---

## 8. DEPENDENCY CHAIN

```
SUCCESS CHAIN:
┌────────────┐
│ File Ingest│ 🔴 BROKEN (No endpoint)
└─────┬──────┘
      │
      v
┌────────────────────┐
│ Data in Qdrant     │ 🟢 Storage OK
└─────┬──────────────┘
      │
      v
┌────────────────────┐
│ Query Preprocessing│ 🔴 MISSING
└─────┬──────────────┘
      │
      v
┌────────────────────┐
│ Hybrid Search      │ 🟢 Works great
└─────┬──────────────┘
      │
      v
┌────────────────────┐
│ LLM Processing     │ 🟢 Solid
└─────┬──────────────┘
      │
      v
┌────────────────────┐
│ Format with Cite   │ 🟡 Exists but unused
└─────┬──────────────┘
      │
      v
┌────────────────────┐
│ Return Response    │ 🟢 Good
└────────────────────┘

BOTTLENECK: 🔴 File ingestion (blocks everything)
WEAKNESS: 🟡 Citation integration (reduces value)
```

---

## Summary

### Current Flow Health: 🟡 YELLOW (CAUTION)
- ✅ 70% working correctly
- 🟡 20% partially working
- ❌ 10% completely broken/missing

### Can it be used now? ❌ NOT FULLY
- Can query: ✅ YES
- Can upload files: ❌ NO
- Get good results: 🟡 MAYBE (with preprocessing)
- Complete feature set: ❌ NO

### Time to fix: ⏱️ 4-5 HOURS
- Critical path: 2-3 hours
- Complete package: 4-5 hours

### Recommendation: 🔧 FIX BEFORE DEPLOYING
