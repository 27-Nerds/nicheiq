"""
Landing Page Generator CLI.

Generates unique, fully-designed HTML landing pages from NicheIQ research reports.
Each run produces a unique design - the LLM chooses colors, structure, and layout.

Usage:
    python -m nicheiq.landing --report output/final_report.json
    python -m nicheiq.landing --report output/final_report.json --output landing.html
    python -m nicheiq.landing --report output/final_report.json --output output/landing.html

Examples:
    # Generate landing page from latest report
    python -m nicheiq.landing --report output/final_report_20241216_143022.json

    # Specify custom output path
    python -m nicheiq.landing --report output/final_report.json --output my_landing.html
"""

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

from ..crews.landing_page_crew import LandingPageCrew
from ..models.research_state import FinalReport


def main():
    """Main entry point for landing page generation."""
    parser = argparse.ArgumentParser(
        description="Generate MVP landing page from NicheIQ research report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m nicheiq.landing --report output/final_report.json
  python -m nicheiq.landing --report output/final_report.json --output my_landing.html
        """
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to final_report.json from NicheIQ research"
    )
    parser.add_argument(
        "--output",
        default="landing_page.html",
        help="Output HTML file path (default: landing_page.html)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    if not args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    # Validate report path
    report_path = Path(args.report)
    if not report_path.exists():
        logger.error(f"Report file not found: {report_path}")
        sys.exit(1)

    # Load report
    logger.info(f"Loading report from: {report_path}")
    try:
        report_data = json.loads(report_path.read_text())
        report = FinalReport(**report_data)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in report file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to parse report: {e}")
        sys.exit(1)

    logger.info(f"Report loaded: {report.selected_solution_name}")
    logger.info(f"Pain points: {len(report.detailed_pain_points) if report.detailed_pain_points else 0}")

    # Generate landing page
    logger.info("Starting landing page generation...")
    logger.info("  - Brand Designer will choose unique colors based on product category")
    logger.info("  - Copywriter will select sections based on solution type")
    logger.info("  - HTML Developer will generate custom layout")

    try:
        crew = LandingPageCrew()
        result = crew.generate(report)
    except Exception as e:
        logger.error(f"Landing page generation failed: {e}")
        raise

    # Save HTML
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.html_output)

    # Print summary
    print("\n" + "=" * 60)
    print("Landing Page Generated Successfully!")
    print("=" * 60)
    print(f"\nOutput: {output_path.absolute()}")
    print(f"\nProduct: {result.page_copy.product_name}")
    print(f"Tagline: {result.page_copy.tagline}")
    print(f"\nDesign Mood: {result.brand_identity.design_mood}")
    print(f"Primary Color: {result.brand_identity.color_primary}")
    print(f"Secondary Color: {result.brand_identity.color_secondary}")
    print(f"\nSections Included ({len(result.sections_generated)}):")
    for section in result.sections_generated:
        print(f"  - {section}")
    print(f"\nSection Selection Reasoning:")
    print(f"  {result.page_copy.section_selection_reasoning}")
    print(f"\nDesign Notes:")
    print(f"  {result.generation_notes}")
    print("\n" + "=" * 60)
    print(f"Open {output_path} in your browser to view the landing page!")
    print("=" * 60)


if __name__ == "__main__":
    main()
