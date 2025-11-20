#!/usr/bin/env python
"""
Test script to verify the improved ingestion and query processing.
"""
import json
import sys
sys.path.insert(0, '/d/Muhusin_Workspace/hybrid_rag_app')

from src.ingestion.ingest_json_dynamic import ingest_json_dynamic

print("=" * 80)
print("Testing Improved JSON Ingestion")
print("=" * 80)

# Test the new ingestion function
result = ingest_json_dynamic(
    'data/sample_docs/cast-metal.json',
    source='cast-metal.json',
    category='finish'
)

print(f"\nIngestion Result:")
print(f"  Chunks Created: {result.get('chunks_created')}")
print(f"  Material: {result.get('material')}")

# Now let's check what was actually ingested
print("\n" + "=" * 80)
print("Verifying Ingested Data")
print("=" * 80)

# Load and display what should have been ingested
with open('data/sample_docs/cast-metal.json', 'r') as f:
    data = json.load(f)

if 'materials' in data:
    print(f"\nMaterials found in JSON: {[m.get('name') for m in data['materials']]}")
    
    for material in data['materials']:
        mat_name = material.get('name')
        print(f"\n{mat_name}:")
        
        if 'colorsFinishes' in material:
            finishes = set()
            for section in material['colorsFinishes']:
                section_name = section.get('name')
                if section_name:
                    finishes.add(section_name)
                    print(f"  - {section_name} ({len(section.get('options', []))} options)")
                
                # Show a few example options
                for idx, opt in enumerate(section.get('options', [])[:2]):
                    print(f"      • {opt.get('name')}")
            
            print(f"  Total finish categories: {len(finishes)}")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)
