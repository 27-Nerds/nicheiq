"""
Pydantic models for Landing Page Generator Crew.

These models define the structured outputs for the 7-agent pipeline:
0. LandingStrategy - Marketing Strategist output (strategy, memorable element)
1. CreativeDirection - Creative Director output (design archetype, visual intensity, layout)
2. BrandIdentity - Brand Designer output (colors, mood, layout)
3. LandingPageCopy - Copywriter output (dynamic sections)
4. HTMLPageResult - HTML Developer output (complete page)
5. AnimatedHTMLResult - Animation Enhancer output (premium motion design)
6. QAReviewResult - QA Reviewer output (validated and fixed HTML)
7. LandingPageResult - Final combined result
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LandingStrategy(BaseModel):
    """Task 0 output: Landing page strategy from Marketing Strategist.

    Provides strategic direction for all downstream agents (Brand Designer,
    Copywriter, HTML Developer). Defines the ONE memorable element that
    will make the page unforgettable.
    """

    model_config = ConfigDict(extra='forbid')

    primary_persona: str = Field(
        ...,
        description="The primary target persona to focus on (from target_personas)"
    )
    primary_persona_reasoning: str = Field(
        ...,
        description="Why this persona is the best target for the landing page"
    )
    key_messaging_angle: str = Field(
        ...,
        description="The main emotional trigger or value prop to lead with (e.g., 'fear of revenue concentration', 'desire for predictability')"
    )
    pain_points_to_emphasize: list[str] = Field(
        ...,
        description="Top 2-3 pain points to emphasize, in order of importance"
    )
    differentiation_hook: str = Field(
        ...,
        description="What makes this product DIFFERENT from competitors (1-2 sentences)"
    )
    recommended_sections: list[str] = Field(
        ...,
        description="Recommended sections in order: hero, problem, solution, how_it_works, social_proof, pricing, comparison, use_cases, faq, cta"
    )
    section_reasoning: str = Field(
        ...,
        description="Why these sections in this order for this specific product"
    )
    memorable_element: str = Field(
        ...,
        description="The ONE thing visitors should remember about this page (e.g., 'oversized statistic showing 5 advertisers = 50% revenue risk')"
    )
    memorable_element_implementation: str = Field(
        ...,
        description="How to implement the memorable element (specific guidance for designers)"
    )
    headline_direction: str = Field(
        ...,
        description="Suggested headline approach: 'problem-first', 'benefit-first', 'question', or 'statistic-led'"
    )
    tone_of_voice: str = Field(
        ...,
        description="Tone: 'professional-authoritative', 'friendly-approachable', 'urgent-direct', or 'technical-precise'"
    )
    conversion_goal: str = Field(
        ...,
        description="Primary conversion goal: 'email_signup', 'waitlist', 'demo_request', or 'free_trial'"
    )
    cta_recommendations: list[str] = Field(
        ...,
        description="3 CTA text options that match the conversion goal and tone"
    )


class CreativeDirection(BaseModel):
    """Task 1 output: Creative direction for landing page design.

    The Creative Director agent analyzes niche positioning, competitive landscape,
    and target persona psychology to create a UNIQUE visual direction. This breaks
    away from templated designs by making autonomous creative decisions based on
    market context. Downstream agents (Brand Designer, HTML Developer) MUST follow.
    """

    model_config = ConfigDict(extra='forbid')

    # Visual Identity
    design_archetype: str = Field(
        ...,
        description="Primary design archetype: 'bold-disruptor', 'premium-authority', 'friendly-accessible', 'technical-precision', 'minimal-elegant', 'vibrant-energetic', 'earth-organic', 'neon-futuristic'"
    )
    visual_intensity: str = Field(
        ...,
        description="Visual boldness level: 'whisper' (minimal), 'conversational' (balanced), 'statement' (bold), 'shout' (maximum impact)"
    )

    # Color Direction (not specific hex - that's brand designer's job)
    color_personality: str = Field(
        ...,
        description="Color mood derived from niche: 'trust-blues', 'growth-greens', 'energy-oranges', 'luxury-purples', 'tech-cyans', 'earth-neutrals', 'neon-accents', 'monochrome-sophisticated'"
    )
    color_temperature: str = Field(
        ...,
        description="Overall warmth: 'cool' (blues/greens), 'warm' (oranges/reds), 'neutral' (grays/earth), 'mixed' (warm accents on cool base)"
    )

    # Layout Direction
    hero_archetype: str = Field(
        ...,
        description="Hero layout pattern: 'split-showcase' (text left, visual right), 'centered-statement' (centered headline, minimal), 'immersive-full' (full-bleed background, overlay text), 'asymmetric-dynamic' (off-center, energetic), 'product-demo' (hero with embedded demo/preview)"
    )
    section_density: str = Field(
        ...,
        description="Content density: 'sparse' (few sections, lots of whitespace), 'balanced' (standard 5-7 sections), 'rich' (many sections, detailed)"
    )
    layout_rhythm: str = Field(
        ...,
        description="Section layout variation: 'uniform' (consistent structure), 'alternating' (left-right pattern), 'progressive' (builds complexity), 'dramatic' (varied heights/widths)"
    )

    # Typography Direction
    typography_personality: str = Field(
        ...,
        description="Font character: 'geometric-modern', 'humanist-friendly', 'technical-precise', 'editorial-elegant', 'playful-rounded', 'bold-impact'"
    )
    heading_scale: str = Field(
        ...,
        description="Headline sizing: 'modest' (text-4xl max), 'standard' (text-5xl-6xl), 'bold' (text-7xl), 'massive' (text-8xl+)"
    )

    # Strategic Reasoning
    archetype_rationale: str = Field(
        ...,
        description="2-3 sentences explaining why this archetype fits the niche, competitive position, and target persona"
    )
    differentiation_visual: str = Field(
        ...,
        description="How the visual direction differentiates from competitors (1-2 sentences)"
    )


class BrandIdentity(BaseModel):
    """Task 1 output: Unique brand identity for the product.

    The Brand Designer agent analyzes the product category and target audience
    to create a unique color palette and design mood. No generic colors -
    every choice must be justified by the specific product.
    """

    model_config = ConfigDict(extra='forbid')

    color_primary: str = Field(
        ...,
        description="Primary brand color as hex code (e.g., #3B82F6). Must match product category."
    )
    color_secondary: str = Field(
        ...,
        description="Secondary/accent color for CTAs as hex code. Must contrast well with primary."
    )
    color_background: str = Field(
        ...,
        description="Page background color as hex code or CSS gradient."
    )
    color_text: str = Field(
        ...,
        description="Primary text color as hex code."
    )
    color_text_muted: str = Field(
        ...,
        description="Secondary/muted text color as hex code."
    )
    font_heading: str = Field(
        ...,
        description="Google Font for headings/headlines (e.g., 'Space Grotesk', 'DM Sans', 'Outfit')"
    )
    font_body: str = Field(
        ...,
        description="Google Font for body text (e.g., 'Inter', 'Source Sans 3', 'Work Sans')"
    )
    font_code: Optional[str] = Field(
        default=None,
        description="Google Font for code/monospace if needed (e.g., 'JetBrains Mono', 'Fira Code')"
    )
    design_mood: str = Field(
        ...,
        description="Design mood: 'minimal-professional', 'bold-vibrant', 'dark-technical', or 'friendly-approachable'"
    )
    gradient_style: Optional[str] = Field(
        default=None,
        description="CSS gradient if using gradient (e.g., 'bg-gradient-to-br from-purple-600 to-blue-500')"
    )
    layout_notes: str = Field(
        ...,
        description="Specific layout recommendations for the HTML developer (spacing, section styles)"
    )
    design_reasoning: str = Field(
        ...,
        description="2-3 sentences explaining WHY these colors/mood fit this specific product"
    )


class LandingPageSection(BaseModel):
    """Individual section content with dynamic section type.

    The Copywriter agent decides which sections to include based on
    the solution type and what will convert best.
    """

    model_config = ConfigDict(extra='forbid')

    section_type: str = Field(
        ...,
        description="Section type: hero, problem, solution, how_it_works, social_proof, pricing, comparison, use_cases, faq, cta"
    )
    headline: str = Field(
        ...,
        description="Section headline text"
    )
    body: str = Field(
        ...,
        description="Section body text (can include markdown for formatting)"
    )
    cta_text: Optional[str] = Field(
        default=None,
        description="Call-to-action button text if section has a CTA"
    )
    items: Optional[list[dict]] = Field(
        default=None,
        description="List items for features, pain points, steps, etc. Each item MUST be an object with 'title' and 'description' keys. Example: [{'title': 'Feature 1', 'description': 'Details...'}]"
    )


class LandingPageCopy(BaseModel):
    """Task 2 output: Dynamically selected sections based on solution type.

    The Copywriter agent analyzes the product and DECIDES which sections
    to include and their order. Not all sections are required - selection
    is based on what will convert best for this specific product.
    """

    model_config = ConfigDict(extra='forbid')

    product_name: str = Field(
        ...,
        description="Product name for the landing page"
    )
    tagline: str = Field(
        ...,
        description="Short tagline/value proposition (1 sentence)"
    )
    sections: list[LandingPageSection] = Field(
        ...,
        description="Ordered list of sections to include. LLM decides which sections and their order based on solution type."
    )
    section_selection_reasoning: str = Field(
        ...,
        description="Explanation of why these sections were chosen and in this order (2-3 sentences)"
    )
    meta_title: str = Field(
        ...,
        description="SEO meta title (50-60 characters)"
    )
    meta_description: str = Field(
        ...,
        description="SEO meta description (150-160 characters)"
    )


class HTMLPageResult(BaseModel):
    """Task 3 output: Complete HTML page.

    The HTML Developer agent generates a complete, production-ready
    HTML file using Tailwind CSS. Each page has unique layouts based
    on the design mood.
    """

    model_config = ConfigDict(extra='forbid')

    html_content: str = Field(
        ...,
        description="Complete HTML file content ready to save and open in browser"
    )
    sections_included: list[str] = Field(
        ...,
        description="List of section types included in the generated HTML"
    )
    design_notes: str = Field(
        ...,
        description="Notes about layout and design choices made based on the brand identity"
    )


class AnimatedHTMLResult(BaseModel):
    """Task 4 output: Enhanced HTML with premium animations.

    The Animation Enhancer agent takes the complete HTML from the HTML Developer
    and enhances it with premium micro-interactions and motion design:
    - Page load animations (staggered fade-ins)
    - Scroll-triggered reveals
    - Hover states (scale, shadow expansion)
    - Micro-interactions (button feedback, form focus)
    """

    model_config = ConfigDict(extra='forbid')

    html_content: str = Field(
        ...,
        description="Complete enhanced HTML with animations (<!DOCTYPE html> to </html>)"
    )
    animations_added: list[str] = Field(
        ...,
        description="List of animation types implemented: page_load, scroll, hover, micro"
    )
    animation_notes: str = Field(
        ...,
        description="2-3 sentences explaining motion design choices"
    )


class QAIssue(BaseModel):
    """Individual QA issue found during visual design review."""

    model_config = ConfigDict(extra='forbid')

    issue_type: str = Field(
        ...,
        description="Category: 'layout_spacing', 'typography', 'responsive'"
    )
    severity: str = Field(
        ...,
        description="Severity level: 'critical', 'major', 'minor'"
    )
    location: str = Field(
        ...,
        description="CSS selector or section where issue was found (e.g., '.hero', '#pricing', 'nav')"
    )
    description: str = Field(
        ...,
        description="Description of what's wrong"
    )
    fix_applied: str = Field(
        ...,
        description="Description of the fix that was applied"
    )


class QAReviewResult(BaseModel):
    """Task 5 output: QA-reviewed and refined HTML.

    The QA Reviewer agent validates the animated HTML against visual design rules,
    identifies issues, and applies fixes to ensure professional quality output.
    """

    model_config = ConfigDict(extra='forbid')

    html_content: str = Field(
        ...,
        description="Refined HTML with all QA fixes applied (<!DOCTYPE html> to </html>)"
    )
    issues_found: list[QAIssue] = Field(
        default_factory=list,
        description="List of issues identified during review"
    )
    issues_fixed_count: int = Field(
        ...,
        description="Number of issues that were fixed"
    )
    quality_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Overall quality score (0-100) based on compliance with design rules"
    )
    passes_qa: bool = Field(
        ...,
        description="True if page meets minimum quality threshold (score >= 80)"
    )
    review_notes: str = Field(
        ...,
        description="2-3 sentences summarizing the QA review findings and improvements"
    )


class LandingPageResult(BaseModel):
    """Final output combining all tasks.

    This is the complete result returned by LandingPageCrew.generate()
    containing strategy, brand identity, copy, HTML, and animations.
    """

    model_config = ConfigDict(extra='forbid')

    landing_strategy: LandingStrategy = Field(
        ...,
        description="Landing strategy created by Marketing Strategist"
    )
    brand_identity: BrandIdentity = Field(
        ...,
        description="Brand identity created by Brand Designer"
    )
    page_copy: LandingPageCopy = Field(
        ...,
        description="Landing page copy created by Copywriter"
    )
    html_output: str = Field(
        ...,
        description="Complete HTML file content with animations"
    )
    sections_generated: list[str] = Field(
        ...,
        description="List of sections included in final output"
    )
    animations_added: list[str] = Field(
        default_factory=list,
        description="List of animation types applied: page_load, scroll, hover, micro"
    )
    generation_notes: str = Field(
        ...,
        description="Combined notes about design, generation, and animation choices"
    )
