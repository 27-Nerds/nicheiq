#!/usr/bin/env python
"""Test DataForSEO API authentication only."""

from src.nicheiq.tools.dataforseo_tool import DataForSEOTool

tool = DataForSEOTool()

# Minimal test with 1 keyword
print("Testing API auth with 1 keyword...")
try:
    result = tool.get_search_volume(["test"])
    if result:
        print(f"✅ API working! Got data: {result[0]}")
    else:
        print("⚠️  API returned empty result")
except Exception as e:
    print(f"❌ API error: {e}")
