#!/usr/bin/env python3
"""Quick test script for API endpoints."""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint."""
    print("\n=== Testing /health ===")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=15)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_ingest():
    """Test ingest endpoint with cast-metal.json."""
    print("\n=== Testing /ingest ===")
    file_path = Path("data/sample_docs/cast-metal.json")
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/json")}
            resp = requests.post(f"{BASE_URL}/ingest", files=files, timeout=30)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_query():
    """Test query endpoint."""
    print("\n=== Testing /query ===")
    try:
        payload = {
            "query": "What are the available finishes for cast metal?",
            "top_k": 5,
            "use_cache": False
        }
        resp = requests.post(f"{BASE_URL}/query", json=payload, timeout=30)
        print(f"Status: {resp.status_code}")
        result = resp.json()
        print(json.dumps({
            "query": result.get("query"),
            "materials_found": result.get("materials_found"),
            "status": "✅ OK" if resp.status_code == 200 else "❌ ERROR"
        }, indent=2))
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting API tests...")
    time.sleep(2)  # Give server time to start if needed
    
    results = {
        "health": test_health(),
        "ingest": test_ingest(),
        "query": test_query()
    }
    
    print("\n" + "="*50)
    print("📊 Test Results:")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print("="*50)
    print(f"\n{'🎉 All tests passed!' if all_passed else '⚠️  Some tests failed.'}")
