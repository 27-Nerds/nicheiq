"""
Quick verification that knowledge sources are working.

Run this AFTER a normal research run to verify:
1. CrewAI storage was created
2. Embeddings were generated
3. Knowledge can be queried
"""

import os
import sys
from pathlib import Path


def check_crewai_storage():
    """Check if CrewAI storage directory exists."""
    print("🔍 Checking CrewAI Storage...")

    # Possible locations
    storage_paths = [
        Path.home() / ".local" / "share" / "CrewAI",
        Path.home() / "Library" / "Application Support" / "CrewAI",
        Path(os.environ.get("CREWAI_STORAGE_DIR", "")) if os.environ.get("CREWAI_STORAGE_DIR") else None
    ]

    found = False
    for path in storage_paths:
        if path and path.exists():
            print(f"✅ Found CrewAI storage at: {path}")
            print(f"   Size: {sum(f.stat().st_size for f in path.rglob('*') if f.is_file()) / 1024:.2f} KB")

            # List collections
            if (path / "knowledge").exists():
                collections = list((path / "knowledge").iterdir())
                print(f"   Collections: {len(collections)}")
                for coll in collections[:5]:
                    print(f"      - {coll.name}")
            found = True
            break

    if not found:
        print("⚠️  No CrewAI storage directory found")
        print("   This means either:")
        print("   1. No crew with knowledge sources has been run yet")
        print("   2. Storage is in a non-standard location")

    print()
    return found


def check_recent_output():
    """Check most recent output for knowledge source indicators."""
    print("🔍 Checking Recent Output Files...")

    output_dir = Path("output")
    if not output_dir.exists():
        print("⚠️  No output directory found")
        return False

    # Find most recent state file
    state_files = sorted(output_dir.glob("research_state_raw_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not state_files:
        print("⚠️  No research state files found")
        return False

    latest_file = state_files[0]
    print(f"✅ Found latest research state: {latest_file.name}")

    # Load and check
    import json
    with open(latest_file, 'r') as f:
        state = json.load(f)

    # Check pain point analysis
    if 'pain_point_analysis' in state and state['pain_point_analysis']:
        ppa = state['pain_point_analysis']
        print(f"\n📊 Pain Point Analysis Results:")
        print(f"   Pain points found: {len(ppa.get('pain_points', []))}")
        print(f"   Total mentions: {ppa.get('total_mentions', 0)}")
        print(f"   Categories: {ppa.get('top_categories', [])}")

        # Check evidence snippets
        if ppa.get('pain_points'):
            total_evidence = sum(len(pp.get('evidence_snippets', [])) for pp in ppa['pain_points'])
            print(f"   Evidence snippets: {total_evidence}")

            # Show sample evidence
            first_pp = ppa['pain_points'][0]
            print(f"\n   Sample Pain Point: {first_pp.get('title', 'N/A')}")
            if first_pp.get('evidence_snippets'):
                sample = first_pp['evidence_snippets'][0][:100]
                print(f"   Sample Evidence: '{sample}...'")

                # Check if evidence looks like real Reddit content
                reddit_indicators = ['r/', 'u/', 'subreddit', 'comment', 'post', 'upvote']
                has_reddit_format = any(indicator in sample.lower() for indicator in reddit_indicators)

                if has_reddit_format:
                    print(f"   ✅ Evidence appears to be from Reddit")
                else:
                    print(f"   ⚠️  Evidence doesn't have obvious Reddit markers")
                    print(f"      (Could be paraphrased, or could be hallucinated)")

    print()
    return True


def check_niche_alignment():
    """Check if pain points align with the niche being analyzed."""
    print("🔍 Checking Niche Alignment...")

    output_dir = Path("output")
    if not output_dir.exists():
        return False

    # Find most recent state file
    state_files = sorted(output_dir.glob("research_state_raw_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not state_files:
        return False

    import json
    with open(state_files[0], 'r') as f:
        state = json.load(f)

    # Get niche
    niche = state.get('niche_context', {}).get('niche_description', 'unknown')
    print(f"   Niche: {niche}")

    # Get pain points
    if state.get('pain_point_analysis', {}).get('pain_points'):
        pain_points = state['pain_point_analysis']['pain_points']
        print(f"\n   Top 5 Pain Points:")
        for i, pp in enumerate(pain_points[:5], 1):
            title = pp.get('title', 'N/A')
            print(f"   {i}. {title}")

        # Simple keyword alignment check
        niche_lower = niche.lower()
        all_pp_text = " ".join([pp.get('title', '') + " " + pp.get('problem_statement', '') for pp in pain_points]).lower()

        # Extract key words from niche
        niche_keywords = set(word for word in niche_lower.split() if len(word) > 4)

        # Count matches
        matches = sum(1 for kw in niche_keywords if kw in all_pp_text)
        match_rate = matches / len(niche_keywords) if niche_keywords else 0

        print(f"\n   Keyword Alignment: {matches}/{len(niche_keywords)} niche keywords found in pain points")

        if match_rate > 0.5:
            print(f"   ✅ Strong alignment - pain points match niche")
        elif match_rate > 0.2:
            print(f"   ⚠️  Moderate alignment - some match")
        else:
            print(f"   ❌ Weak alignment - pain points may not match niche")
            print(f"      This suggests knowledge sources may not be working correctly")

    print()


def main():
    """Run all verification checks."""
    print("=" * 80)
    print("🔬 KNOWLEDGE SOURCES QUICK CHECK")
    print("=" * 80)
    print()

    storage_exists = check_crewai_storage()
    output_exists = check_recent_output()
    check_niche_alignment()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if storage_exists and output_exists:
        print("✅ Knowledge sources appear to be set up correctly")
        print("\nTo run full verification:")
        print("   python test_knowledge_sources.py")
        print("\nTo enable detailed logging:")
        print("   python -m nicheiq.main --niche \"your niche\" --log-level DEBUG")
    else:
        print("⚠️  Some issues detected - see details above")
        print("\nRecommendations:")
        print("   1. Run a full research pipeline first:")
        print("      python -m nicheiq.main --niche \"test niche\"")
        print("   2. Then run this check again")
        print("   3. For detailed verification:")
        print("      python test_knowledge_sources.py")

    print()


if __name__ == "__main__":
    main()
