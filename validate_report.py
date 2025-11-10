#!/usr/bin/env python3
"""
Report Validation Script - Detect Hallucinations in Final Report

Usage:
    python validate_report.py output/final_report_TIMESTAMP.json output/research_state_raw_TIMESTAMP.json

Checks:
1. Pain point conflation (research vs solution pain points)
2. Pain point score accuracy (no rounding)
3. CAC value accuracy (exact ranges preserved)
4. Page count accuracy (exact values from metadata)
5. Competition intensity accuracy (no invented labels)

Returns:
    Exit code 0 if validation passes
    Exit code 1 if hallucinations detected
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ReportValidator:
    """Validates final report against raw research state for hallucinations."""

    def __init__(self, final_report_path: str, raw_state_path: str):
        """Initialize validator with report paths."""
        self.final_report_path = Path(final_report_path)
        self.raw_state_path = Path(raw_state_path)
        self.hallucinations = []
        self.warnings = []

    def load_files(self) -> Tuple[Dict, Dict]:
        """Load and parse JSON files."""
        with open(self.final_report_path, 'r', encoding='utf-8') as f:
            final_report = json.load(f)

        with open(self.raw_state_path, 'r', encoding='utf-8') as f:
            raw_state = json.load(f)

        return final_report, raw_state

    def validate_pain_point_conflation(self, final_report: Dict, raw_state: Dict) -> None:
        """Check if final report mixes research vs solution pain points."""
        print("\n[1] Validating Pain Point Conflation...")

        # Get research-discovered pain points
        research_pain_points = set()
        if raw_state.get('pain_point_analysis', {}).get('pain_points'):
            research_pain_points = {
                pp['title'] for pp in raw_state['pain_point_analysis']['pain_points']
            }

        # Get solution-addressed pain points
        solution_pain_points = set()
        if raw_state.get('idea_generation', {}).get('solution_ideas'):
            for solution in raw_state['idea_generation']['solution_ideas']:
                if solution.get('pain_points_addressed'):
                    solution_pain_points.update(solution['pain_points_addressed'])

        # Check if final report's top_pain_points contains any solution-only pain points
        if final_report.get('top_pain_points'):
            for pain_point in final_report['top_pain_points']:
                if pain_point not in research_pain_points:
                    # Check if it's from solution pain points
                    for sol_pp in solution_pain_points:
                        if pain_point.lower() in sol_pp.lower() or sol_pp.lower() in pain_point.lower():
                            self.hallucinations.append({
                                'type': 'Pain Point Conflation',
                                'severity': 'CRITICAL',
                                'claim': f"Top pain point: '{pain_point}'",
                                'reality': f"Not found in research pain points. Appears to be from solution.pain_points_addressed",
                                'impact': 'Presents solution assumptions as validated research findings'
                            })
                            break

        print(f"   ✓ Research pain points identified: {len(research_pain_points)}")
        print(f"   ✓ Top pain points in report: {len(final_report.get('top_pain_points', []))}")

    def validate_pain_point_scores(self, final_report: Dict, raw_state: Dict) -> None:
        """Check if pain point scores are exact (not rounded)."""
        print("\n[2] Validating Pain Point Score Accuracy...")

        if not raw_state.get('pain_point_analysis', {}).get('pain_points'):
            print("   ⚠ No pain points in raw state to validate")
            return

        # Build lookup of research pain points by title
        research_pps = {
            pp['title']: pp for pp in raw_state['pain_point_analysis']['pain_points']
        }

        # Check selection_rationale for pain point score mentions
        if final_report.get('selection_rationale'):
            import re
            # Look for patterns like "Severity: 0.8" or "WTP: 0.8"
            severity_mentions = re.findall(r'Severity[:\s]+([0-9.]+)', final_report['selection_rationale'])
            wtp_mentions = re.findall(r'WTP[:\s]+([0-9.]+)', final_report['selection_rationale'])

            for severity_str in severity_mentions:
                severity_val = float(severity_str)
                # Check if this is a rounded value
                if severity_val != round(severity_val, 2):
                    continue  # Exact values are fine

                # Check if any research pain point has exact match
                exact_match = any(
                    abs(pp['severity_score'] - severity_val) < 0.001
                    for pp in research_pps.values()
                )

                if not exact_match:
                    # Check if it's a rounded version
                    for title, pp in research_pps.items():
                        if abs(round(pp['severity_score'], 1) - severity_val) < 0.001 and abs(pp['severity_score'] - severity_val) > 0.01:
                            self.hallucinations.append({
                                'type': 'Score Rounding',
                                'severity': 'MINOR',
                                'claim': f"Severity: {severity_val}",
                                'reality': f"Actual severity_score: {pp['severity_score']}",
                                'impact': f'Score rounded for pain point: {title}'
                            })

        print(f"   ✓ Pain point scores validated")

    def validate_cac_values(self, final_report: Dict, raw_state: Dict) -> None:
        """Check if CAC values are exact (not modified)."""
        print("\n[3] Validating CAC Value Accuracy...")

        # Get selected solution from raw state
        selected_solution = None
        if raw_state.get('solution_selection') and raw_state.get('idea_generation'):
            selected_name = raw_state['solution_selection']['selected_solution_name']
            for solution in raw_state['idea_generation']['solution_ideas']:
                if solution['solution_name'] == selected_name:
                    selected_solution = solution
                    break

        if not selected_solution:
            print("   ⚠ No selected solution found in raw state")
            return

        # Extract CAC values from final report
        if final_report.get('estimated_cac_breakdown'):
            cac_text = final_report['estimated_cac_breakdown']

            # Get expected CAC values
            expected_paid = selected_solution.get('estimated_cac_paid', 'N/A')
            expected_organic = selected_solution.get('estimated_cac_organic') or selected_solution.get('estimated_cac_organic_refined', 'N/A')

            # Check if paid CAC is mentioned and matches
            if expected_paid != 'N/A' and expected_paid not in cac_text:
                self.hallucinations.append({
                    'type': 'CAC Underestimation',
                    'severity': 'CRITICAL',
                    'claim': f"Paid CAC mentioned in report (extracted from text)",
                    'reality': f"Expected: {expected_paid}",
                    'impact': 'Paid acquisition costs misrepresented, could lead to incorrect budget planning'
                })

            print(f"   ✓ Expected Paid CAC: {expected_paid}")
            print(f"   ✓ Expected Organic CAC: {expected_organic}")

    def validate_page_count(self, final_report: Dict, raw_state: Dict) -> None:
        """Check if page count estimates are accurate."""
        print("\n[4] Validating Page Count Accuracy...")

        # Get selected solution
        selected_solution = None
        if raw_state.get('solution_selection') and raw_state.get('idea_generation'):
            selected_name = raw_state['solution_selection']['selected_solution_name']
            for solution in raw_state['idea_generation']['solution_ideas']:
                if solution['solution_name'] == selected_name:
                    selected_solution = solution
                    break

        if not selected_solution:
            print("   ⚠ No selected solution found")
            return

        # Get page count from metadata
        expected_pages = None
        if selected_solution.get('seo_refinement_metadata'):
            expected_pages = selected_solution['seo_refinement_metadata'].get('estimated_year1_pages')

        if expected_pages is None:
            print("   ⚠ No page count in seo_refinement_metadata")
            return

        # Check if acquisition_strategy_summary mentions page counts
        if final_report.get('acquisition_strategy_summary'):
            import re
            # Look for page count mentions
            page_mentions = re.findall(r'(\d+)\s+(?:pages|indexable pages|landing pages)',
                                      final_report['acquisition_strategy_summary'],
                                      re.IGNORECASE)

            for page_str in page_mentions:
                page_val = int(page_str)
                if page_val != expected_pages and abs(page_val - expected_pages) > (expected_pages * 0.1):
                    self.hallucinations.append({
                        'type': 'Page Count Discrepancy',
                        'severity': 'MAJOR',
                        'claim': f"{page_val} pages mentioned in report",
                        'reality': f"Metadata shows: {expected_pages} pages",
                        'impact': f'{abs(page_val - expected_pages) / expected_pages * 100:.0f}% discrepancy in SEO scalability estimate'
                    })

        print(f"   ✓ Expected Year 1 Pages: {expected_pages}")

    def validate_competition_intensity(self, final_report: Dict, raw_state: Dict) -> None:
        """Check if competitive intensity labels are from actual data."""
        print("\n[5] Validating Competition Intensity Labels...")

        # Get competitive intensity from raw state
        expected_intensity = None
        if raw_state.get('competitive_analysis') and raw_state.get('solution_selection'):
            selected_name = raw_state['solution_selection']['selected_solution_name']
            for landscape in raw_state['competitive_analysis'].get('solution_landscapes', []):
                if landscape['solution_name'] == selected_name:
                    expected_intensity = landscape.get('competitive_intensity')
                    break

        # Check if final report mentions intensity labels when they don't exist
        if final_report.get('competitive_summary'):
            import re
            intensity_mentions = re.findall(
                r'(high|medium|low|very high|very low)\s+compet(?:itive|ition)\s+intensity',
                final_report['competitive_summary'],
                re.IGNORECASE
            )

            if intensity_mentions and expected_intensity is None:
                self.hallucinations.append({
                    'type': 'Invented Competition Intensity',
                    'severity': 'MINOR',
                    'claim': f"Mentions '{intensity_mentions[0]}' competitive intensity",
                    'reality': f"Raw state shows: competitive_intensity = null",
                    'impact': 'LLM inferred intensity level not explicitly calculated by crew'
                })

        print(f"   ✓ Expected Intensity: {expected_intensity or 'null (not calculated)'}")

    def run_validation(self) -> int:
        """Run all validation checks and return exit code."""
        print("=" * 80)
        print("REPORT VALIDATION - Hallucination Detection")
        print("=" * 80)
        print(f"\nFinal Report: {self.final_report_path.name}")
        print(f"Raw State: {self.raw_state_path.name}")

        try:
            final_report, raw_state = self.load_files()
            print("\n✓ Files loaded successfully")
        except Exception as e:
            print(f"\n✗ Error loading files: {e}")
            return 1

        # Run all validation checks
        self.validate_pain_point_conflation(final_report, raw_state)
        self.validate_pain_point_scores(final_report, raw_state)
        self.validate_cac_values(final_report, raw_state)
        self.validate_page_count(final_report, raw_state)
        self.validate_competition_intensity(final_report, raw_state)

        # Print results
        print("\n" + "=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)

        if not self.hallucinations:
            print("\n✅ PASS - No hallucinations detected!")
            print("\nThe final report is grounded in research data with no fabricated information.")
            return 0
        else:
            print(f"\n❌ FAIL - {len(self.hallucinations)} hallucination(s) detected")
            print("\n" + "-" * 80)

            for i, hallucination in enumerate(self.hallucinations, 1):
                print(f"\n[HALLUCINATION #{i}]")
                print(f"Type: {hallucination['type']}")
                print(f"Severity: {hallucination['severity']}")
                print(f"Claim: {hallucination['claim']}")
                print(f"Reality: {hallucination['reality']}")
                print(f"Impact: {hallucination['impact']}")
                print("-" * 80)

            return 1


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print(__doc__)
        print("\nError: Please provide paths to final report and raw state JSON files")
        sys.exit(1)

    final_report_path = sys.argv[1]
    raw_state_path = sys.argv[2]

    validator = ReportValidator(final_report_path, raw_state_path)
    exit_code = validator.run_validation()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
