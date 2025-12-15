"""
Visualization Generation for NicheIQ Reports

Generates charts and visual analytics from research data using Plotly.
Exports in multiple formats: PNG (for PDF), JSON (for web), SVG (scalable).
"""

from pathlib import Path

from loguru import logger

try:
    import plotly.express as px  # noqa: F401
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly not available - visualizations will be skipped")

class ChartGenerator:
    """
    Generate charts for NicheIQ reports.

    All charts are generated as:
    - PNG (for PDF embedding)
    - JSON (for interactive web viewing)
    """

    def __init__(self, output_dir: Path):
        """
        Initialize chart generator.

        Args:
            output_dir: Directory to save generated charts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pain_point_matrix(
        self,
        pain_points: list,
        output_name: str = "pain_point_matrix"
    ) -> tuple[str, str | None]:
        """
        Generate scatter plot: Severity vs Willingness-to-Pay.

        Args:
            pain_points: List of PainPoint objects
            output_name: Base name for output files

        Returns:
            Tuple of (png_path, json_path) or None if failed
        """
        if not PLOTLY_AVAILABLE or not pain_points:
            return None

        try:
            # Extract data
            titles = [pp.title[:40] + "..." if len(pp.title) > 40 else pp.title for pp in pain_points]
            severity = [pp.severity_score for pp in pain_points]
            wtp = [pp.willingness_to_pay for pp in pain_points]

            # Create scatter plot
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=severity,
                y=wtp,
                mode='markers+text',
                marker=dict(
                    size=15,
                    color=[(s + w) / 2 for s, w in zip(severity, wtp)],  # Color by priority
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Priority")
                ),
                text=[str(i+1) for i in range(len(pain_points))],
                textposition="middle center",
                textfont=dict(color='white', size=10),
                hovertext=titles,
                hoverinfo='text+x+y'
            ))

            # Add quadrant lines
            fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5)
            fig.add_vline(x=0.5, line_dash="dash", line_color="gray", opacity=0.5)

            # Layout
            fig.update_layout(
                title="Pain Point Priority Matrix",
                xaxis_title="Severity Score",
                yaxis_title="Willingness to Pay",
                xaxis=dict(range=[0, 1.05]),
                yaxis=dict(range=[0, 1.05]),
                height=500,
                showlegend=False,
                font=dict(size=12)
            )

            # Save PNG
            png_path = self.output_dir / f"{output_name}.png"
            fig.write_image(str(png_path), width=800, height=500)

            # Save JSON
            json_path = self.output_dir / f"{output_name}.json"
            fig.write_json(str(json_path))

            logger.info(f"[OK] Pain point matrix saved: {png_path}")
            return (str(png_path), str(json_path))

        except Exception as e:
            logger.warning(f"Failed to generate pain point matrix: {e}")
            return None

    def generate_keyword_opportunity_chart(
        self,
        tier_counts: dict,
        output_name: str = "keyword_opportunity"
    ) -> tuple[str, str | None]:
        """
        Generate bar chart showing keyword distribution by tier.

        Args:
            tier_counts: Dict like {"Tier 1": 5, "Tier 2": 10, "Tier 3": 50}
            output_name: Base name for output files

        Returns:
            Tuple of (png_path, json_path) or None if failed
        """
        if not PLOTLY_AVAILABLE or not tier_counts:
            return None

        try:
            tiers = list(tier_counts.keys())
            counts = list(tier_counts.values())

            # Color coding
            colors = ['#2ecc71', '#3498db', '#f39c12', '#95a5a6'][:len(tiers)]

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=tiers,
                y=counts,
                marker_color=colors,
                text=counts,
                textposition='auto',
                hovertemplate='%{x}: %{y} keywords<extra></extra>'
            ))

            fig.update_layout(
                title="Keyword Opportunity by Tier",
                xaxis_title="Keyword Tier",
                yaxis_title="Number of Keywords",
                height=400,
                showlegend=False,
                font=dict(size=12)
            )

            # Save PNG
            png_path = self.output_dir / f"{output_name}.png"
            fig.write_image(str(png_path), width=700, height=400)

            # Save JSON
            json_path = self.output_dir / f"{output_name}.json"
            fig.write_json(str(json_path))

            logger.info(f"[OK] Keyword opportunity chart saved: {png_path}")
            return (str(png_path), str(json_path))

        except Exception as e:
            logger.warning(f"Failed to generate keyword opportunity chart: {e}")
            return None

    def generate_competitive_landscape(
        self,
        competitors: list,
        output_name: str = "competitive_landscape"
    ) -> tuple[str, str | None]:
        """
        Generate competitive landscape visualization.

        Simple bar chart showing competitor count by category.

        Args:
            competitors: List of competitor objects
            output_name: Base name for output files

        Returns:
            Tuple of (png_path, json_path) or None if failed
        """
        if not PLOTLY_AVAILABLE or not competitors:
            return None

        try:
            # Group by type if available
            types = {}
            for comp in competitors:
                comp_type = getattr(comp, 'competitor_type', 'Unknown')
                types[comp_type] = types.get(comp_type, 0) + 1

            categories = list(types.keys())
            counts = list(types.values())

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=categories,
                y=counts,
                marker_color='#e74c3c',
                text=counts,
                textposition='auto',
                hovertemplate='%{x}: %{y} competitors<extra></extra>'
            ))

            fig.update_layout(
                title="Competitive Landscape by Category",
                xaxis_title="Competitor Type",
                yaxis_title="Number of Competitors",
                height=400,
                showlegend=False,
                font=dict(size=12)
            )

            # Save PNG
            png_path = self.output_dir / f"{output_name}.png"
            fig.write_image(str(png_path), width=700, height=400)

            # Save JSON
            json_path = self.output_dir / f"{output_name}.json"
            fig.write_json(str(json_path))

            logger.info(f"[OK] Competitive landscape chart saved: {png_path}")
            return (str(png_path), str(json_path))

        except Exception as e:
            logger.warning(f"Failed to generate competitive landscape: {e}")
            return None

    def generate_implementation_timeline(
        self,
        first_30_days,
        output_name: str = "implementation_timeline"
    ) -> tuple[str, str] | None:
        """
        Generate horizontal bar chart showing 30-day implementation timeline.

        Args:
            first_30_days: First30DaysPlaybook with week actions
            output_name: Base name for output files

        Returns:
            Tuple of (png_path, json_path) or None if failed
        """
        if not PLOTLY_AVAILABLE or not first_30_days:
            return None

        try:
            # Build timeline data
            weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]
            action_counts = [
                len(first_30_days.week_1_actions) if first_30_days.week_1_actions else 0,
                len(first_30_days.week_2_actions) if first_30_days.week_2_actions else 0,
                len(first_30_days.week_3_actions) if first_30_days.week_3_actions else 0,
                len(first_30_days.week_4_actions) if first_30_days.week_4_actions else 0
            ]

            # Get first action from each week as hover labels
            week_labels = [
                first_30_days.week_1_actions[0][:50] + "..." if first_30_days.week_1_actions else "No actions",
                first_30_days.week_2_actions[0][:50] + "..." if first_30_days.week_2_actions else "No actions",
                first_30_days.week_3_actions[0][:50] + "..." if first_30_days.week_3_actions else "No actions",
                first_30_days.week_4_actions[0][:50] + "..." if first_30_days.week_4_actions else "No actions"
            ]

            fig = go.Figure()

            # Horizontal bar chart with gradient colors
            colors = ['#27ae60', '#2980b9', '#8e44ad', '#e74c3c']

            fig.add_trace(go.Bar(
                y=weeks,
                x=action_counts,
                orientation='h',
                marker_color=colors,
                text=action_counts,
                textposition='inside',
                hovertext=week_labels,
                hoverinfo='text+x'
            ))

            fig.update_layout(
                title="30-Day Implementation Timeline",
                xaxis_title="Number of Actions",
                yaxis_title="Week",
                height=350,
                showlegend=False,
                font=dict(size=12)
            )

            # Save PNG
            png_path = self.output_dir / f"{output_name}.png"
            fig.write_image(str(png_path), width=700, height=350)

            # Save JSON
            json_path = self.output_dir / f"{output_name}.json"
            fig.write_json(str(json_path))

            logger.info(f"[OK] Implementation timeline saved: {png_path}")
            return (str(png_path), str(json_path))

        except Exception as e:
            logger.warning(f"Failed to generate implementation timeline: {e}")
            return None
