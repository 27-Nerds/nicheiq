#!/usr/bin/env python3
"""
Report Validation Script - Detect Hallucinations in Final Report

Usage:
    python validate_report.py output/final_report_TIMESTAMP.json output/research_state_raw_TIMESTAMP.json

Validation Philosophy (Pattern #7):
- Trust the LLM for style, validate only for data integrity
- Focus on: score references, calculations, cross-stage consistency
- Ignore: word counts, style preferences, vocabulary

Checks:
1. Pain point conflation (research vs solution pain points)
2. Pain point score accuracy (no rounding)
3. CAC value accuracy (exact ranges preserved)
4. Page count accuracy (exact values from metadata)
5. Competition intensity accuracy (no invented labels)
6. Go/No-Go verdict references actual scores (NEW - CRITICAL)
7. Executive metrics match raw data (NEW)
8. Analytics calculations are correct (NEW)

Returns:
    Exit code 0 if validation passes
    Exit code 1 if hallucinations detected
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Import settings for validation thresholds
try:
    from src.nicheiq.config.settings import settings
    USE_SETTINGS = True
except ImportError:
    print("Warning: Could not import settings. Using hardcoded defaults.")
    USE_SETTINGS = False

    # Fallback class with defaults
    class FallbackSettings:
        pain_point_high_priority_threshold = 0.7
        competitive_intensity_low_threshold = 3
        competitive_intensity_high_threshold = 8
        verdict_go_avg_score = 0.75
        verdict_go_min_individual_score = 0.7
        verdict_conditional_avg_score = 0.60
        verdict_conditional_min_individual_score = 0.55

    settings = FallbackSettings()


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
                # Extract title from formatted string (format: "Title - Description (Severity: X, WTP: Y)")
                pain_point_title = pain_point.split(' - ')[0].strip() if ' - ' in pain_point else pain_point.strip()

                if pain_point_title not in research_pain_points:
                    # Check if it's from solution pain points
                    for sol_pp in solution_pain_points:
                        if pain_point_title.lower() in sol_pp.lower() or sol_pp.lower() in pain_point_title.lower():
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
        # Priority 1: Check seo_enrichment (Stage 9.5 refined values)
        # Priority 2: Check selected_solution (fallback if refinement disabled)
        expected_pages = None

        # First check seo_enrichment (the actual refined values)
        if raw_state.get('seo_enrichment') and raw_state['seo_enrichment'].get('seo_refinement_metadata'):
            expected_pages = raw_state['seo_enrichment']['seo_refinement_metadata'].get('estimated_year1_pages')
        # Fallback to solution in idea_generation (only has placeholders normally)
        elif selected_solution.get('seo_refinement_metadata'):
            expected_pages = selected_solution['seo_refinement_metadata'].get('estimated_year1_pages')

        if expected_pages is None:
            print("   ⚠ No page count in seo_refinement_metadata (SEO refinement may be disabled)")
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

    def validate_go_no_go_verdict(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Validate go/no-go verdict references actual scores (Pattern #7 - CRITICAL).

        Checks:
        1. Verdict rationale must reference actual scores (not hallucinated)
        2. Score keywords present: "market fit", "competitive", "feasibility", "seo"
        3. Verdict matches score thresholds from settings
        4. Flags temporal claims without data support
        """
        print("\n[6] Validating Go/No-Go Verdict (CRITICAL)...")

        if not final_report.get('executive_dashboard'):
            print("   ⚠ No executive dashboard found - skipping verdict validation")
            return

        dashboard = final_report['executive_dashboard']
        if not dashboard.get('go_no_go_verdict'):
            print("   ⚠ No go/no-go verdict found")
            return

        verdict_data = dashboard['go_no_go_verdict']
        verdict = verdict_data.get('verdict', '')
        rationale = verdict_data.get('rationale', '').lower()

        # Check 1: Rationale must reference scores
        score_keywords = ['market fit', 'competitive', 'feasibility', 'seo', 'score']
        has_score_reference = any(keyword in rationale for keyword in score_keywords)

        if not has_score_reference:
            self.hallucinations.append({
                'type': 'Verdict Hallucination',
                'severity': 'CRITICAL',
                'claim': f"Verdict: {verdict}",
                'reality': "Rationale does not reference actual scores",
                'impact': 'Verdict may be hallucinated rather than data-driven - violates Pattern #7'
            })

        # Check 2: Temporal claims without data
        temporal_patterns = [
            r'will\s+grow',
            r'is\s+growing',
            r'trending\s+up',
            r'increasing\s+demand',
            r'market\s+is\s+expanding'
        ]
        import re
        for pattern in temporal_patterns:
            if re.search(pattern, rationale, re.IGNORECASE):
                self.warnings.append({
                    'type': 'Temporal Claim',
                    'severity': 'MINOR',
                    'claim': f"Rationale contains temporal claim: '{pattern}'",
                    'reality': "Temporal trends not validated by research data",
                    'impact': 'May be LLM speculation rather than data-supported finding'
                })

        # Check 3: Verdict matches score thresholds (if key_metrics available)
        if dashboard.get('key_metrics'):
            metrics = dashboard['key_metrics']
            scores = [
                metrics.get('market_fit_score', 0),
                metrics.get('competitive_advantage_score', 0),
                metrics.get('technical_feasibility_score', 0),
                metrics.get('seo_potential_score', 0)
            ]

            avg_score = sum(scores) / len(scores) if scores else 0
            min_critical_scores = min([
                metrics.get('market_fit_score', 0),
                metrics.get('technical_feasibility_score', 0)
            ])

            # Validate verdict logic
            if verdict == "Go":
                if avg_score < settings.verdict_go_avg_score:
                    self.hallucinations.append({
                        'type': 'Verdict Mismatch',
                        'severity': 'MAJOR',
                        'claim': f"Verdict: Go (avg score: {avg_score:.2f})",
                        'reality': f"Avg score ({avg_score:.2f}) < threshold ({settings.verdict_go_avg_score})",
                        'impact': 'Verdict does not match configured thresholds'
                    })
                if min_critical_scores < settings.verdict_go_min_individual_score:
                    self.hallucinations.append({
                        'type': 'Verdict Mismatch',
                        'severity': 'MAJOR',
                        'claim': f"Verdict: Go (min critical: {min_critical_scores:.2f})",
                        'reality': f"Min score ({min_critical_scores:.2f}) < threshold ({settings.verdict_go_min_individual_score})",
                        'impact': 'Critical scores too low for Go verdict'
                    })

        print(f"   ✓ Verdict: {verdict}")
        print(f"   ✓ Score references in rationale: {has_score_reference}")

    def validate_executive_metrics(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Validate executive dashboard metrics match raw data (Pattern #7).

        Checks:
        1. key_metrics scores exist in raw state
        2. confidence_score calculation is correct
        3. core_pain_point matches top pain point from analysis
        """
        print("\n[7] Validating Executive Metrics...")

        if not final_report.get('executive_dashboard'):
            print("   ⚠ No executive dashboard found")
            return

        dashboard = final_report['executive_dashboard']

        # Check 1: Validate confidence_score calculation
        if dashboard.get('key_metrics'):
            metrics = dashboard['key_metrics']
            market_fit = metrics.get('market_fit_score', 0)
            competitive = metrics.get('competitive_advantage_score', 0)
            # confidence_score is at dashboard level, not in key_metrics
            confidence = dashboard.get('confidence_score', 0)

            expected_confidence = (market_fit + competitive) / 2
            if abs(confidence - expected_confidence) > 0.01:
                self.hallucinations.append({
                    'type': 'Calculation Error',
                    'severity': 'MAJOR',
                    'claim': f"Confidence score: {confidence:.2f}",
                    'reality': f"Expected: (market_fit + competitive) / 2 = {expected_confidence:.2f}",
                    'impact': 'Confidence score calculation incorrect'
                })

        # Check 2: Core pain point matches research
        if dashboard.get('core_pain_point') and raw_state.get('pain_point_analysis'):
            core_pp = dashboard['core_pain_point']['title']
            research_pps = raw_state['pain_point_analysis'].get('pain_points', [])

            if research_pps:
                top_pp_title = research_pps[0]['title']
                if core_pp.lower() != top_pp_title.lower():
                    self.warnings.append({
                        'type': 'Pain Point Mismatch',
                        'severity': 'MINOR',
                        'claim': f"Core pain point: {core_pp}",
                        'reality': f"Top research pain point: {top_pp_title}",
                        'impact': 'Core pain point may not be the highest priority from research'
                    })

        print(f"   ✓ Executive metrics validated")

    def validate_analytics_consistency(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Validate analytics calculations are mathematically correct (Pattern #7).

        Checks:
        1. overall_opportunity_score = avg of 4 scores
        2. seo_analytics.total_keywords = sum of tier counts
        3. pain_point_analytics quadrant counts add up
        """
        print("\n[8] Validating Analytics Consistency...")

        # Check 1: Overall opportunity score
        if final_report.get('market_analytics') and final_report.get('executive_dashboard'):
            market_analytics = final_report['market_analytics']
            dashboard = final_report['executive_dashboard']

            if dashboard.get('key_metrics'):
                metrics = dashboard['key_metrics']
                scores = [
                    metrics.get('market_fit_score', 0),
                    metrics.get('competitive_advantage_score', 0),
                    metrics.get('technical_feasibility_score', 0),
                    metrics.get('seo_potential_score', 0)
                ]

                expected_avg = sum(scores) / len(scores) if scores else 0
                actual_avg = market_analytics.get('overall_opportunity_score', 0)

                if abs(expected_avg - actual_avg) > 0.01:
                    self.hallucinations.append({
                        'type': 'Calculation Error',
                        'severity': 'MAJOR',
                        'claim': f"Overall opportunity score: {actual_avg:.2f}",
                        'reality': f"Expected: avg of 4 scores = {expected_avg:.2f}",
                        'impact': 'Overall opportunity score calculation incorrect'
                    })

        # Check 2: SEO tier totals
        if final_report.get('seo_analytics'):
            seo = final_report['seo_analytics']

            # Access direct fields (not nested dict)
            tier_sum = sum([
                seo.get('tier0_count', 0),
                seo.get('tier1_count', 0),
                seo.get('tier2_count', 0),
                seo.get('tier3_count', 0),
                seo.get('tier4_count', 0)
            ])

            total_keywords = seo.get('total_keywords', 0)

            if tier_sum != total_keywords:
                self.hallucinations.append({
                    'type': 'Calculation Error',
                    'severity': 'MAJOR',
                    'claim': f"Total keywords: {total_keywords}",
                    'reality': f"Sum of tier counts: {tier_sum}",
                    'impact': 'SEO keyword totals do not add up'
                })

        # Check 3: Pain point quadrant totals
        if final_report.get('pain_point_analytics'):
            pp_analytics = final_report['pain_point_analytics']
            quadrant_dist = pp_analytics.get('quadrant_distribution', {})

            # Use actual keys from _compute_pain_point_analytics
            quadrant_sum = sum([
                quadrant_dist.get('high_severity_high_wtp', 0),
                quadrant_dist.get('high_severity_low_wtp', 0),
                quadrant_dist.get('low_severity_high_wtp', 0),
                quadrant_dist.get('low_severity_low_wtp', 0)
            ])

            total_pain_points = pp_analytics.get('total_pain_points', 0)

            if quadrant_sum != total_pain_points:
                self.hallucinations.append({
                    'type': 'Calculation Error',
                    'severity': 'MAJOR',
                    'claim': f"Total pain points: {total_pain_points}",
                    'reality': f"Sum of quadrant counts: {quadrant_sum}",
                    'impact': 'Pain point quadrant totals do not add up'
                })

        print(f"   ✓ Analytics calculations validated")

    # ========================================================================
    # PHASE 1: CRITICAL VALIDATION CHECKS
    # ========================================================================

    def validate_solution_selection_consistency(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #1: Verify selected solution exists in idea_generation AND competitive_analysis.

        Catches hallucination where selected solution name doesn't exist in prior stage data.
        Ensures competitive analysis was performed for selected solution.
        """
        print("\n[9] Validating Solution Selection Consistency...")

        if not raw_state.get('solution_selection') or not raw_state['solution_selection'].get('selected_solution_name'):
            print("   ⚠ No solution selection data found")
            return

        selected_name = raw_state['solution_selection']['selected_solution_name']

        # Check 1: Selected solution exists in idea_generation
        if raw_state.get('idea_generation') and raw_state['idea_generation'].get('solution_ideas'):
            solution_names = [s.get('solution_name', '') for s in raw_state['idea_generation']['solution_ideas']]
            if selected_name not in solution_names:
                self.hallucinations.append({
                    'type': 'Solution Name Hallucination',
                    'severity': 'CRITICAL',
                    'claim': f"Selected solution: {selected_name}",
                    'reality': f"Not found in idea_generation. Available: {solution_names[:3]}",
                    'impact': 'Selected solution was not generated by ideation crew - data integrity compromised'
                })

        # Check 2: Selected solution has competitive analysis
        if raw_state.get('competitive_analysis') and raw_state['competitive_analysis'].get('solution_landscapes'):
            competitive_solutions = [
                l.get('solution_name', '')
                for l in raw_state['competitive_analysis']['solution_landscapes']
            ]
            if selected_name not in competitive_solutions:
                self.hallucinations.append({
                    'type': 'Missing Competitive Analysis',
                    'severity': 'MAJOR',
                    'claim': f"Selected solution: {selected_name}",
                    'reality': f"No competitive landscape found. Analyzed: {competitive_solutions[:3]}",
                    'impact': 'Competitive summary may not reflect actual selected solution analysis'
                })

        print(f"   ✓ Selected solution: {selected_name}")

    def validate_alternative_solution_scores(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #3: Verify alternative solutions have valid scores (0.0-1.0, not all None).

        Catches score fabrication or failed score lookup. Ensures pivot decision criteria
        are data-driven.
        """
        print("\n[10] Validating Alternative Solution Scores...")

        alternatives = final_report.get('alternative_solutions', [])
        if not alternatives:
            print("   ⚠ No alternative solutions found")
            return

        for alt in alternatives:
            solution_name = alt.get('solution_name', 'Unknown')
            scores = {
                'market_fit_score': alt.get('market_fit_score'),
                'technical_feasibility_score': alt.get('technical_feasibility_score'),
                'competitive_advantage_score': alt.get('competitive_advantage_score'),
                'seo_growth_potential_score': alt.get('seo_growth_potential_score')
            }

            # Check 1: Not all None
            if all(s is None for s in scores.values()):
                self.hallucinations.append({
                    'type': 'Alternative Solution Missing Scores',
                    'severity': 'MAJOR',
                    'claim': f"Alternative: {solution_name}",
                    'reality': "All scores are None - no evaluation data",
                    'impact': 'Cannot compare alternatives to selected solution without scores'
                })
                continue

            # Check 2: Scores in valid range
            for score_name, score in scores.items():
                if score is not None and not (0.0 <= score <= 1.0):
                    self.hallucinations.append({
                        'type': 'Invalid Score Range',
                        'severity': 'MAJOR',
                        'claim': f"{solution_name}: {score_name} = {score}",
                        'reality': "Score must be 0.0-1.0",
                        'impact': 'Invalid score range indicates data corruption'
                    })

        print(f"   ✓ {len(alternatives)} alternative solutions validated")

    # ========================================================================
    # PHASE 2: MAJOR VALIDATION CHECKS
    # ========================================================================

    def validate_runner_up_count_consistency(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #2: Verify len(alternative_solutions) matches len(runner_up_solutions).

        Catches data assembly errors where runner-ups are claimed but not detailed.
        """
        print("\n[11] Validating Runner-Up Count Consistency...")

        runner_up_names = final_report.get('runner_up_solutions', [])
        alternatives = final_report.get('alternative_solutions', [])

        if not runner_up_names:
            print("   ⚠ No runner-up solutions listed")
            return

        expected_count = min(len(runner_up_names), 2)  # Top 2 runners
        actual_count = len(alternatives) if alternatives else 0

        if actual_count < expected_count:
            self.hallucinations.append({
                'type': 'Alternative Solutions Missing',
                'severity': 'MAJOR',
                'claim': f"{len(runner_up_names)} runner-up solutions listed",
                'reality': f"Only {actual_count} alternatives detailed (expected {expected_count})",
                'impact': 'Runner-up analysis incomplete - missing pivot recommendations'
            })

        print(f"   ✓ {len(runner_up_names)} runner-ups, {actual_count} detailed alternatives")

    def validate_enrichment_merge_completeness(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #6: Verify Stage 8.85 and 9.5 enrichments were applied to selected solution.

        Catches report generator merge failures for solution_refinement and seo_enrichment.
        """
        print("\n[12] Validating Enrichment Merge Completeness...")

        selected_solution = final_report.get('selected_solution_details', {})
        if not selected_solution:
            print("   ⚠ No selected solution details found")
            return

        enrichment_checks = []

        # Check keyword enrichment (Stage 8.85)
        if raw_state.get('solution_refinement'):
            refinement = raw_state['solution_refinement']

            if refinement.get('geographic_priorities') and not selected_solution.get('keyword_geographic_priorities'):
                self.hallucinations.append({
                    'type': 'Keyword Enrichment Not Applied',
                    'severity': 'MAJOR',
                    'claim': "Selected solution should have keyword_geographic_priorities",
                    'reality': "Stage 8.85 refinement has geographic_priorities but not merged into solution",
                    'impact': 'Keyword insights from Stage 8.85 lost - geographic expansion data missing'
                })
            else:
                enrichment_checks.append("geographic priorities")

            if refinement.get('feature_priorities') and not selected_solution.get('keyword_feature_priorities'):
                self.hallucinations.append({
                    'type': 'Feature Enrichment Not Applied',
                    'severity': 'MAJOR',
                    'claim': "Selected solution should have keyword_feature_priorities",
                    'reality': "Stage 8.85 refinement has feature_priorities but not merged",
                    'impact': 'Feature prioritization from keyword data lost'
                })
            else:
                enrichment_checks.append("feature priorities")

        # Check SEO enrichment (Stage 9.5)
        if raw_state.get('seo_enrichment'):
            enrichment = raw_state['seo_enrichment']

            if enrichment.get('seo_refinement_metadata') and enrichment['seo_refinement_metadata'].get('seo_scalability_score_refined') is not None:
                if selected_solution.get('seo_refinement_metadata'):
                    if selected_solution['seo_refinement_metadata'].get('seo_scalability_score_refined') is None:
                        self.hallucinations.append({
                            'type': 'SEO Enrichment Not Applied',
                            'severity': 'MAJOR',
                            'claim': "Selected solution should have seo_scalability_score_refined",
                            'reality': "Stage 9.5 enrichment has refined score but not merged",
                            'impact': 'SEO score refinement from keyword data lost - using initial estimate'
                        })
                    else:
                        enrichment_checks.append("SEO scalability score")

        if enrichment_checks:
            print(f"   ✓ Enrichments applied: {', '.join(enrichment_checks)}")
        else:
            print("   ⚠ No enrichments found to validate")

    def validate_evidence_quote_attribution(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #9: Verify pain point quotes have valid post IDs in social_content.

        Ensures traceability claims are accurate. Catches fabricated attribution.
        """
        print("\n[13] Validating Evidence Quote Attribution...")

        evidence = final_report.get('evidence_appendix', {})
        if not evidence or not evidence.get('pain_point_quote_sources'):
            print("   ⚠ No evidence appendix found")
            return

        # Build set of valid post IDs
        valid_post_ids = set()
        if raw_state.get('social_content', {}).get('reddit_posts'):
            valid_post_ids.update(p.get('post_id', '') for p in raw_state['social_content']['reddit_posts'])
        if raw_state.get('social_content', {}).get('twitter_threads'):
            valid_post_ids.update(t.get('thread_id', '') for t in raw_state['social_content']['twitter_threads'])

        invalid_count = 0
        total_quotes = 0

        for pp_evidence in evidence['pain_point_quote_sources']:
            for quote_source in pp_evidence.get('quotes_with_sources', []):
                total_quotes += 1
                post_id = quote_source.get('post_id', '')

                if post_id and post_id != 'unknown' and post_id not in valid_post_ids:
                    invalid_count += 1
                    self.hallucinations.append({
                        'type': 'Invalid Quote Attribution',
                        'severity': 'MAJOR',
                        'claim': f"Quote attributed to post_id: {post_id}",
                        'reality': f"Post ID not found in social_content ({len(valid_post_ids)} valid IDs)",
                        'impact': f"Evidence traceability broken for pain point: {pp_evidence.get('pain_point_title', 'Unknown')}"
                    })

        if invalid_count == 0:
            print(f"   ✓ All {total_quotes} quotes have valid attribution")
        else:
            print(f"   ⚠ {invalid_count}/{total_quotes} quotes have invalid attribution")

    def validate_keyword_stage_consistency(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #5: Verify Stage 9 keyword count >= Stage 8.8 validated count.

        Stage 8.8 validates seeds, Stage 9 expands to 150+ keywords.
        If Stage 9 has fewer keywords, expansion failed.
        """
        print("\n[14] Validating Keyword Stage Consistency...")

        kw_validation = raw_state.get('keyword_validation_results', [])
        if not kw_validation or not raw_state.get('solution_selection'):
            print("   ⚠ No keyword validation data found")
            return

        selected_name = raw_state['solution_selection'].get('selected_solution_name', '')

        # Find validation result for selected solution
        selected_validation = next(
            (v for v in kw_validation if v.get('solution_name') == selected_name),
            None
        )

        if not selected_validation:
            print("   ⚠ No validation data for selected solution")
            return

        stage_8_8_count = selected_validation.get('validated_count', 0)
        stage_9_count = final_report.get('seo_analytics', {}).get('total_keywords', 0)

        # Stage 9 should expand keywords, not reduce
        if stage_9_count < stage_8_8_count:
            self.hallucinations.append({
                'type': 'Keyword Count Regression',
                'severity': 'MAJOR',
                'claim': f"Stage 9 SEO strategy: {stage_9_count} keywords",
                'reality': f"Stage 8.8 validation: {stage_8_8_count} keywords - Stage 9 should expand, not reduce",
                'impact': 'Keyword expansion failed - SEO strategy may be incomplete'
            })

        print(f"   ✓ Stage 8.8: {stage_8_8_count} validated, Stage 9: {stage_9_count} total")

    def validate_gtm_channel_evidence(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #4: Verify GTM blueprint channels reference actual research data.

        Reddit channels should reference actual subreddits from research.
        SEO channels should reference actual keyword counts.
        """
        print("\n[15] Validating GTM Channel Evidence...")

        gtm = final_report.get('go_to_market_blueprint', {})
        if not gtm or not gtm.get('recommended_channels'):
            print("   ⚠ No GTM blueprint found")
            return

        import re

        for channel in gtm['recommended_channels']:
            channel_name = channel.get('channel_name', '')
            rationale = channel.get('rationale', '')

            # Check Reddit channels reference actual subreddits
            if 'Reddit' in channel_name and 'r/' in channel_name:
                match = re.search(r'r/(\w+)', channel_name)
                if match:
                    subreddit = match.group(1)

                    # Check if subreddit appears in research
                    if raw_state.get('social_content', {}).get('reddit_posts'):
                        actual_subreddits = {post.get('subreddit', '') for post in raw_state['social_content']['reddit_posts']}
                        if subreddit not in actual_subreddits:
                            self.hallucinations.append({
                                'type': 'GTM Channel Hallucination',
                                'severity': 'MAJOR',
                                'claim': f"Recommended channel: {channel_name}",
                                'reality': f"r/{subreddit} not found in research. Actual: {list(actual_subreddits)[:3]}",
                                'impact': 'Marketing channel recommendation not grounded in research data'
                            })

            # Check SEO channels reference actual keyword data
            if 'SEO' in channel_name and 'keyword' in rationale.lower():
                keyword_match = re.search(r'(\d+)\s+(?:keywords?|Tier)', rationale)
                if keyword_match and raw_state.get('seo_strategy_report'):
                    claimed_count = int(keyword_match.group(1))
                    actual_tier1 = len(raw_state['seo_strategy_report'].get('tier_1_keywords', []))

                    # Allow ±20% variance
                    if claimed_count > actual_tier1 * 1.2:
                        self.hallucinations.append({
                            'type': 'GTM Keyword Count Fabrication',
                            'severity': 'MAJOR',
                            'claim': f"SEO channel mentions {claimed_count} keywords",
                            'reality': f"Actual Tier 1 count: {actual_tier1}",
                            'impact': 'SEO opportunity may be overstated in GTM blueprint'
                        })

        print(f"   ✓ {len(gtm['recommended_channels'])} channels validated")

    # ========================================================================
    # PHASE 3: MINOR VALIDATION CHECKS (Quality Improvements)
    # ========================================================================

    def validate_seo_tier_distribution(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #4: Validate SEO tier distribution for anomalies.

        Flags unusual patterns like no Tier 0/1/2, single tier >90%, missing geographic tier.
        """
        print("\n[16] Validating SEO Tier Distribution...")

        seo = final_report.get('seo_analytics', {})
        if not seo or seo.get('total_keywords', 0) == 0:
            print("   ⚠ No SEO analytics data found")
            return

        total = seo['total_keywords']
        tier_counts = [
            seo.get('tier0_count', 0),
            seo.get('tier1_count', 0),
            seo.get('tier2_count', 0),
            seo.get('tier3_count', 0),
            seo.get('tier4_count', 0)
        ]

        # Check 1: At least one of Tier 0/1/2 should exist (quick wins)
        if sum(tier_counts[:3]) == 0 and total > 0:
            self.hallucinations.append({
                'type': 'SEO Tier Distribution Anomaly',
                'severity': 'MINOR',
                'claim': "No Tier 0/1/2 keywords found",
                'reality': f"{total} total keywords but none classified as quick wins",
                'impact': 'SEO strategy lacks immediate opportunity identification'
            })

        # Check 2: No single tier should dominate (>90%)
        for i, count in enumerate(tier_counts):
            if count / total > 0.9:
                self.hallucinations.append({
                    'type': 'SEO Tier Imbalance',
                    'severity': 'MINOR',
                    'claim': f"Tier {i} contains {count}/{total} keywords ({count/total*100:.0f}%)",
                    'reality': "Expected more diverse tier distribution",
                    'impact': 'May indicate tier classification issue or very niche keyword set'
                })

        # Check 3: Geographic (Tier 3) should exist if total > 50
        if total > 50 and tier_counts[3] == 0:
            # This is informational - not an error
            pass  # Don't flag as this can be valid for some niches

        tier_summary = ", ".join([f"T{i}: {c}" for i, c in enumerate(tier_counts) if c > 0])
        print(f"   ✓ Tier distribution: {tier_summary}")

    def _extract_domain_terms(self, solution_name: str, top_pain_points: list) -> list[str]:
        """
        Extract niche-specific domain terms from solution for validation.

        Returns list of domain-specific terms (>4 chars) that indicate specificity.
        """
        import re

        terms = []

        # From solution name (remove common words)
        name_words = solution_name.lower().split()
        stopwords = {'the', 'a', 'an', 'for', 'and', 'or', 'index', 'platform', 'tool', 'app', 'your'}
        terms.extend([w for w in name_words if w not in stopwords and len(w) > 4])

        # From top pain points (extract meaningful words - simplified: words >5 chars)
        for pp in top_pain_points[:3]:
            pp_words = re.findall(r'\b[a-z]{5,}\b', str(pp).lower())
            terms.extend(pp_words[:3])  # Top 3 words per pain point

        return list(set(terms))  # Deduplicate

    def validate_next_steps_specificity(self, final_report: Dict, raw_state: Dict) -> None:
        """
        Check #8: Validate next steps contain specific references vs generic steps.

        Detects generic LLM fallback when strategic synthesis fails.
        """
        print("\n[17] Validating Next Steps Specificity...")

        next_steps = final_report.get('next_steps', [])
        if not next_steps or len(next_steps) == 0:
            print("   ⚠ No next steps found")
            return

        selected_name = raw_state.get('solution_selection', {}).get('selected_solution_name', '')

        # Extract product name from full solution title (before colon if present)
        product_name = selected_name.split(':')[0].strip() if ':' in selected_name else selected_name

        # Extract domain-specific terms for validation
        top_pain_points = final_report.get('top_pain_points', [])
        domain_terms = self._extract_domain_terms(selected_name, top_pain_points)

        # Get project type if available
        project_type = ''
        if raw_state.get('solution_selection') and raw_state['solution_selection'].get('selected_solution'):
            project_type = raw_state['solution_selection']['selected_solution'].get('project_type', '')

        # Generic phrases to detect
        generic_phrases = [
            'review detailed research',
            'validate pain points',
            'design and develop mvp',
            'implement seo strategy',
            'set up data sourcing',
            'launch beta version'
        ]

        import re

        specific_count = 0
        for step in next_steps:
            step_lower = step.lower()

            # Check if step contains specific data references
            has_specific_data = any([
                # EXISTING patterns (from previous fixes)
                product_name.lower() in step_lower,  # Solution name (product only)
                re.search(r'tier \d', step_lower),  # SEO tier reference
                re.search(r'\d+\s+keywords?', step_lower),  # Keyword count
                re.search(r'\d+\s+(?:indexable\s+)?pages?', step_lower),  # Pages/indexable pages count
                re.search(r'r/\w+', step_lower),  # Subreddit reference
                re.search(r'\d+\s+(?:pain point|competitor)', step_lower),  # Count references

                # NEW patterns (Phase 1 improvements)
                # Process milestones
                re.search(r'\bmvp\b', step_lower),  # Minimum viable product
                re.search(r'validation interviews?', step_lower),  # User research
                re.search(r'user research|surveys?|outreach', step_lower),  # Research activities

                # Strategy/architecture terms
                re.search(r'programmatic seo', step_lower),  # SEO strategy
                project_type and project_type.lower() in step_lower,  # Project type (aggregator, directory, etc.)

                # Domain-specific terms (dynamically extracted from solution/pain points)
                any(term.lower() in step_lower for term in domain_terms if len(term) > 4),

                # Feature/capability references
                re.search(r'\b(?:reliability|transparency|annotations?|repair|cost|data|index)\b', step_lower),

                # Role references
                re.search(r'\b(?:technician|expert|specialist)\b', step_lower)
            ])

            if has_specific_data:
                specific_count += 1

        # If <20% of steps have specific data, it's too generic
        specificity_ratio = specific_count / len(next_steps)
        if specificity_ratio < 0.2:
            self.hallucinations.append({
                'type': 'Generic Next Steps',
                'severity': 'MINOR',
                'claim': f"{len(next_steps)} next steps provided",
                'reality': f"Only {specific_count}/{len(next_steps)} reference specific research data ({specificity_ratio*100:.0f}%)",
                'impact': 'Next steps are generic - not tailored to this specific solution/niche'
            })

        print(f"   ✓ {specific_count}/{len(next_steps)} steps have specific data ({specificity_ratio*100:.0f}% specificity)")

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

        # NEW: Pattern #7 validations (data integrity)
        self.validate_go_no_go_verdict(final_report, raw_state)
        self.validate_executive_metrics(final_report, raw_state)
        self.validate_analytics_consistency(final_report, raw_state)

        # PHASE 1: CRITICAL validation checks
        self.validate_solution_selection_consistency(final_report, raw_state)
        self.validate_alternative_solution_scores(final_report, raw_state)

        # PHASE 2: MAJOR validation checks
        self.validate_runner_up_count_consistency(final_report, raw_state)
        self.validate_enrichment_merge_completeness(final_report, raw_state)
        self.validate_evidence_quote_attribution(final_report, raw_state)
        self.validate_keyword_stage_consistency(final_report, raw_state)
        self.validate_gtm_channel_evidence(final_report, raw_state)

        # PHASE 3: MINOR validation checks (Quality)
        self.validate_seo_tier_distribution(final_report, raw_state)
        self.validate_next_steps_specificity(final_report, raw_state)

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
