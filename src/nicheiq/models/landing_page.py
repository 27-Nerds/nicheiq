"""
Pydantic models for Landing Page Generator Crew.

These models define the structured outputs for the 8-agent pipeline:
0. LandingStrategy - Marketing Strategist output (strategy, memorable element)
1. CreativeDirection - Creative Director output (design archetype, visual intensity, layout)
2. VisualDesignSpec - Visual Designer output (card treatments, visual surprises, animation personality)
3. BrandIdentity - Brand Designer output (colors, mood, layout)
4. LandingPageCopy - Copywriter output (dynamic sections)
5. HTMLPageResult - HTML Developer output (complete page)
6. AnimatedHTMLResult - Animation Enhancer output (premium motion design)
7. QAReviewResult - QA Reviewer output (validated and fixed HTML)
8. LandingPageResult - Final combined result
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LandingStrategy(BaseModel):
    """Task 0 output: Landing page strategy from Marketing Strategist.

    Provides strategic direction for all downstream agents (Brand Designer,
    Copywriter, HTML Developer). Defines the ONE memorable element that
    will make the page unforgettable.
    """

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

    # Visual Identity
    design_archetype: str = Field(
        ...,
        description="Design character that fits this product (e.g., bold-disruptor, premium-authority, minimal-elegant, technical-precision, or your own hybrid)"
    )
    visual_intensity: str = Field(
        ...,
        description="Visual boldness level (e.g., whisper, conversational, statement, shout, or custom level)"
    )

    # Color Direction (not specific hex - that's brand designer's job)
    color_personality: str = Field(
        ...,
        description="Color mood that fits the product story (e.g., trust-blues, growth-greens, luxury-purples, or your own palette direction)"
    )
    color_temperature: str = Field(
        ...,
        description="Overall color warmth (e.g., cool, warm, neutral, mixed, or custom balance)"
    )

    # Layout Direction
    hero_archetype: str = Field(
        ...,
        description="Hero layout pattern (e.g., split-showcase, centered-statement, immersive-full, asymmetric-dynamic, or custom layout)"
    )
    section_density: str = Field(
        ...,
        description="Content density level (e.g., sparse, balanced, rich, or custom density)"
    )
    layout_rhythm: str = Field(
        ...,
        description="Section layout variation (e.g., uniform, alternating, progressive, dramatic, or custom rhythm)"
    )

    # Typography Direction
    typography_personality: str = Field(
        ...,
        description="Font character that matches the product (e.g., geometric-modern, humanist-friendly, editorial-elegant, or custom style)"
    )
    heading_scale: str = Field(
        ...,
        description="Headline sizing approach (e.g., modest, standard, bold, massive, or custom scale)"
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
    design_inspiration: Optional[str] = Field(
        default=None,
        description="Optional: Real-world landing pages or design patterns that inspired this direction. Helps document creative thinking."
    )


class CardTreatment(BaseModel):
    """Visual treatment specification for a card type.

    The Visual Designer specifies how different card types should look,
    enabling varied treatments across the page.
    """

    model_config = ConfigDict(extra='ignore')

    card_type: str = Field(
        ...,
        description="Card purpose: 'feature', 'pain_point', 'step', 'benefit', 'pricing', 'faq'"
    )
    visual_elements: list[str] = Field(
        ...,
        description="Visual elements to include: 'emoji_icon', 'accent_bar_left', 'numbered_badge', 'gradient_bg', 'decorative_border', 'shadow_lift'"
    )
    emphasis_level: str = Field(
        ...,
        description="Visual emphasis: 'primary' (bold), 'secondary' (subtle), 'tertiary' (minimal)"
    )
    icon_suggestion: Optional[str] = Field(
        default=None,
        description="Suggested emoji or unicode icon if using icons (e.g., '🚀', '⚡', '✓')"
    )


class MemorableElementVisual(BaseModel):
    """Visual specification for the page's memorable element.

    The Landing Strategy defines WHAT the memorable element is.
    This model defines HOW it should look visually.
    """

    model_config = ConfigDict(extra='ignore')

    implementation_type: str = Field(
        ...,
        description="Visual approach: 'hero_stat', 'callout_box', 'sidebar_highlight', 'full_bleed_graphic', 'floating_badge', 'artifact_screenshot'"
    )
    placement: str = Field(
        ...,
        description="Position on page: 'hero_right', 'hero_below', 'section_standalone', 'inline_with_copy'"
    )
    color_treatment: str = Field(
        ...,
        description="Color emphasis: 'accent_dominant', 'primary_subtle', 'high_contrast', 'muted_elegant'"
    )
    typography_scale: str = Field(
        ...,
        description="Text sizing: 'massive' (text-8xl+), 'large' (text-6xl), 'standard' (text-4xl)"
    )
    animation_entry: str = Field(
        ...,
        description="Entry animation: 'fade_up', 'scale_in', 'slide_from_right', 'pulse_attention', 'none'"
    )


class VisualSurprise(BaseModel):
    """A deliberate design convention break.

    Visual surprises make the page feel hand-crafted rather than template-generated.
    Each surprise documents what convention is being broken and why.
    """

    model_config = ConfigDict(extra='ignore')

    convention_broken: str = Field(
        ...,
        description="What typical pattern we're deliberately breaking"
    )
    creative_choice: str = Field(
        ...,
        description="What we're doing instead (the surprise)"
    )
    section_applied: str = Field(
        ...,
        description="Which section this convention break applies to"
    )


class SectionWeight(BaseModel):
    """Visual weight for a page section."""

    section: str = Field(..., description="Section name, e.g. 'hero', 'problem', 'features'")
    weight: str = Field(..., description="Visual weight: 'dominant', 'standard', or 'subtle'")


class SectionContent(BaseModel):
    """Content composition for a page section."""

    section: str = Field(..., description="Section name, e.g. 'hero', 'problem'")
    composition: str = Field(..., description="Content description, e.g. 'headline + form + artifact'")


class SectionItem(BaseModel):
    """Item within a landing page section (feature, pain point, step, etc.)."""

    title: str = Field(..., description="Item title")
    description: str = Field(..., description="Item description")


class VisualDesignSpec(BaseModel):
    """Task 2.5 output: Visual design specifications from Visual Designer.

    The Visual Designer interprets the Creative Director's abstract vision
    into specific visual decisions. This bridges abstract creative direction
    and concrete implementation.
    """

    model_config = ConfigDict(extra='ignore')

    # Card Strategy
    card_treatments: list[CardTreatment] = Field(
        ...,
        description="Visual treatment specifications for each card type on the page"
    )
    card_variation_approach: str = Field(
        ...,
        description="How cards vary: 'by_type' (features differ from pain points), 'by_position' (first card differs), 'alternating' (odd/even), 'progressive' (builds intensity)"
    )

    # Memorable Element
    memorable_element_visual: MemorableElementVisual = Field(
        ...,
        description="Visual specification for the ONE memorable element from landing strategy"
    )

    # Visual Surprises
    visual_surprises: list[VisualSurprise] = Field(
        ...,
        description="2-3 deliberate convention breaks to make the page feel unique"
    )

    # Section Hierarchy
    section_visual_weights: list[SectionWeight] = Field(
        ...,
        description="Visual weight per section as a list of objects. Options for weight: 'dominant', 'standard', 'subtle'"
    )

    # Animation Personality
    animation_personality: str = Field(
        ...,
        description="Animation character: 'playful' (bouncy easing, stagger), 'professional' (smooth, minimal), 'dramatic' (slow reveals, scale), 'technical' (precise, fast)"
    )

    # Design Reasoning
    visual_design_rationale: str = Field(
        ...,
        description="2-3 sentences explaining the visual strategy and why these choices fit the product"
    )

    # Page Structure (architecture decisions)
    page_blueprint: str = Field(
        ...,
        description="Wireframe-level page structure: section order, layout type (grid/stacked), and key structural decisions"
    )

    hero_composition: str = Field(
        ...,
        description="Hero content: what elements belong (headline, form, artifact) and what doesn't (feature cards if artifact demonstrates them)"
    )

    section_composition: list[SectionContent] = Field(
        ...,
        description="Per-section content as a list of objects, e.g. [{section: 'hero', composition: 'headline + form + artifact, no feature cards'}]"
    )

    content_redundancy_notes: str = Field(
        ...,
        description="What NOT to include because it's redundant: 'artifact shows compliance steps, so don't list as cards'"
    )


class BrandIdentity(BaseModel):
    """Task 1 output: Unique brand identity for the product.

    The Brand Designer agent analyzes the product category and target audience
    to create a unique color palette and design mood. No generic colors -
    every choice must be justified by the specific product.
    """

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

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
    items: Optional[list[SectionItem]] = Field(
        default=None,
        description="List items for features, pain points, steps, etc. Each item has 'title' and 'description' fields."
    )


class LandingPageCopy(BaseModel):
    """Task 2 output: Dynamically selected sections based on solution type.

    The Copywriter agent analyzes the product and DECIDES which sections
    to include and their order. Not all sections are required - selection
    is based on what will convert best for this specific product.
    """

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

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

    model_config = ConfigDict(extra='ignore')

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
