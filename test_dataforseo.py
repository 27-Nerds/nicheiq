"""
Quick test script for DataForSEO API integration.
Run with: uv run python test_dataforseo.py
"""

from src.nicheiq.tools.dataforseo_tool import DataForSEOTool
from src.nicheiq.config.settings import settings
from loguru import logger


def test_api_connection():
    """Test basic API connection and credentials."""
    print("=" * 80)
    print("Testing DataForSEO API Connection")
    print("=" * 80)

    # Check credentials are loaded
    print(f"DataForSEO Login: {settings.dataforseo_login}")
    print(
        f"DataForSEO Password: {'*' * len(settings.dataforseo_password) if settings.dataforseo_password else 'NOT SET'}"
    )
    print()


def test_keyword_expansion():
    """Test keyword expansion with sample keywords."""
    print("=" * 80)
    print("Test 1: Keyword Expansion")
    print("=" * 80)

    tool = DataForSEOTool()
    seed_keywords = ["AI tools", "content creator"]

    print(f"Testing with seed keywords: {seed_keywords}")
    print()

    try:
        expanded = tool.expand_keywords(seed_keywords)
        print(f"✓ Success! Expanded to {len(expanded)} keywords")
        print("\nSample expanded keywords:")
        for kw in expanded[:5]:
            print(
                f"  - {kw['keyword']}: {kw['search_volume']} volume, {kw['competition']:.2f} competition"
            )
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_search_volume():
    """Test search volume API with sample keywords."""
    print("\n" + "=" * 80)
    print("Test 2: Search Volume")
    print("=" * 80)

    tool = DataForSEOTool()
    keywords = ["ai video editor", "content creation tool", "video generator"]

    print(f"Testing with keywords: {keywords}")
    print()

    try:
        metrics = tool.get_search_volume(keywords)
        print(f"✓ Success! Retrieved metrics for {len(metrics)} keywords")
        print("\nKeyword metrics:")
        for kw in metrics:
            print(f"  - {kw['keyword']}")
            print(f"    Volume: {kw['search_volume']:,}")
            print(f"    Competition: {kw['competition']:.2f} (index: {kw['competition_index']})")
            print(f"    CPC: ${kw['cpc']:.2f}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_full_workflow():
    """Test complete keyword research workflow."""
    print("\n" + "=" * 80)
    print("Test 3: Full Keyword Research Workflow")
    print("=" * 80)

    tool = DataForSEOTool()
    seed_keywords = ["AI content tools"]

    print(f"Testing full workflow with: {seed_keywords}")
    print()

    try:
        keyword_models = tool.process_keywords(seed_keywords, expand=True)
        print(f"✓ Success! Processed {len(keyword_models)} total keywords")

        # Show opportunity breakdown
        high = [k for k in keyword_models if k.opportunity_level.value == "high"]
        medium = [k for k in keyword_models if k.opportunity_level.value == "medium"]
        low = [k for k in keyword_models if k.opportunity_level.value == "low"]

        print(f"\nOpportunity Breakdown:")
        print(f"  High: {len(high)} keywords")
        print(f"  Medium: {len(medium)} keywords")
        print(f"  Low: {len(low)} keywords")

        if high:
            print("\nTop high-opportunity keywords:")
            for kw in sorted(high, key=lambda k: k.search_volume, reverse=True)[:5]:
                print(f"  - {kw.keyword}: {kw.search_volume:,} volume, {kw.competition:.2f} comp")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔍 DataForSEO API Integration Test\n")

    # Test 1: Check credentials
    test_api_connection()

    # Test 2: Keyword expansion
    success_expand = test_keyword_expansion()

    # Test 3: Search volume
    success_volume = test_search_volume()

    # Test 4: Full workflow
    success_full = test_full_workflow()

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Keyword Expansion: {'✓ PASS' if success_expand else '✗ FAIL'}")
    print(f"Search Volume:     {'✓ PASS' if success_volume else '✗ FAIL'}")
    print(f"Full Workflow:     {'✓ PASS' if success_full else '✗ FAIL'}")

    if all([success_expand, success_volume, success_full]):
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed - check errors above")
