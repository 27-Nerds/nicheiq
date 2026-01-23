"""
JSON-LD Schema Generators for SEO Implementation.

This module generates JSON-LD structured data from templates and solution context,
replacing LLM-generated JSON-LD which was 80% static and caused issues:
- Token waste
- Truncation risk
- Repetition loops
- Template variable errors

The LLM now provides schema type selections + strategic rationale.
Python generates actual JSON-LD code deterministically.
"""

import json
from typing import TYPE_CHECKING, Optional

from loguru import logger

if TYPE_CHECKING:
    from ...models.seo_strategy import SchemaSelectionLight


def _slugify(name: str) -> str:
    """
    Convert solution name to URL-friendly slug.

    Args:
        name: Solution name (e.g., "Visa Work Rights Matrix")

    Returns:
        URL-friendly slug (e.g., "visaworkrightsmatrix")
    """
    return (
        name.lower()
        .replace(" ", "")
        .replace("—", "")
        .replace("-", "")
        .replace("_", "")
    )


def generate_organization_schema(
    solution_name: str,
    description: str,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate Organization JSON-LD schema.

    Args:
        solution_name: Name of the solution/company
        description: Value proposition or description
        base_url: Optional custom base URL

    Returns:
        JSON-LD Organization schema dict
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": solution_name,
        "url": url,
        "logo": f"{url}/assets/logo.png",
        "description": description[:200] if description else solution_name,
        "address": {"@type": "PostalAddress", "addressCountry": "US"},
        "sameAs": [f"https://www.linkedin.com/company/{_slugify(solution_name)}"],
    }


def generate_service_schema(
    solution_name: str,
    description: str,
    pricing: Optional[dict] = None,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate Service JSON-LD schema.

    Args:
        solution_name: Name of the solution/service
        description: Service description
        pricing: Optional pricing info dict with 'price' key
        base_url: Optional custom base URL

    Returns:
        JSON-LD Service schema dict
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"
    schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": f"{solution_name} Pro",
        "serviceType": "SaaS Subscription",
        "description": description[:300] if description else f"{solution_name} service",
        "provider": {
            "@type": "Organization",
            "name": solution_name,
            "url": url,
        },
    }
    if pricing:
        schema["offers"] = {
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": str(pricing.get("price", "9.00")),
            "url": f"{url}/pricing/",
        }
    return schema


def generate_faq_schema(
    questions: list[str],
    solution_name: str,
    niche: str,
) -> dict:
    """
    Generate FAQPage JSON-LD schema.

    Args:
        questions: List of FAQ question strings
        solution_name: Solution name for answer context
        niche: Market niche for answer context

    Returns:
        JSON-LD FAQPage schema dict
    """
    # Generate default questions if none provided
    default_questions = [
        f"What is {solution_name}?",
        f"How does {solution_name} work?",
        f"What are the benefits of using {solution_name}?",
        f"How much does {solution_name} cost?",
        f"Is {solution_name} right for me?",
    ]
    question_list = questions[:5] if questions else default_questions[:5]

    faq_items = []
    for q in question_list:
        # Format question if it's just a topic
        if "?" not in q:
            q = f"What is {q} and how does it relate to {niche}?"

        faq_items.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"Detailed answer about {q.lower().rstrip('?')} related to {niche}. "
                        f"Visit {solution_name} for comprehensive information and resources."
            }
        })

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_items,
    }


def generate_breadcrumb_schema(
    base_url: str,
    path_items: Optional[list[tuple[str, str]]] = None,
) -> dict:
    """
    Generate BreadcrumbList JSON-LD schema.

    Args:
        base_url: Base URL for the site
        path_items: Optional list of (name, path) tuples

    Returns:
        JSON-LD BreadcrumbList schema dict
    """
    # Default breadcrumb structure
    default_items = [
        ("Home", "/"),
        ("Features", "/features/"),
        ("Pricing", "/pricing/"),
    ]
    items_list = path_items or default_items

    items = []
    for i, (name, path) in enumerate(items_list, 1):
        items.append({
            "@type": "ListItem",
            "position": i,
            "name": name,
            "item": f"{base_url.rstrip('/')}{path}",
        })

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def generate_article_schema(
    title: str,
    description: str,
    base_url: str,
    solution_name: Optional[str] = None,
) -> dict:
    """
    Generate Article JSON-LD schema.

    Args:
        title: Article title
        description: Article description
        base_url: Base URL for the site
        solution_name: Optional solution name for publisher

    Returns:
        JSON-LD Article schema dict
    """
    # Generate URL-friendly slug from title
    slug = title.lower().replace(" ", "-").replace("'", "").replace('"', "")[:50]
    publisher_name = solution_name or title.split()[0] if title else "Editorial Team"

    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110] if title else "Article",  # Google recommends < 110 chars
        "description": description[:200] if description else title,
        "url": f"{base_url.rstrip('/')}/blog/{slug}/",
        "author": {"@type": "Organization", "name": "Editorial Team"},
        "publisher": {
            "@type": "Organization",
            "name": publisher_name,
            "logo": {
                "@type": "ImageObject",
                "url": f"{base_url.rstrip('/')}/assets/logo.png"
            }
        },
        "datePublished": "2025-01-01",
        "dateModified": "2025-01-15",
    }


def generate_webpage_schema(
    title: str,
    description: str,
    url: str,
) -> dict:
    """
    Generate WebPage JSON-LD schema.

    Args:
        title: Page title
        description: Page description
        url: Full page URL

    Returns:
        JSON-LD WebPage schema dict
    """
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "description": description[:200] if description else title,
        "url": url,
    }


def generate_review_schema(
    solution_name: str,
    rating: float = 4.8,
    review_count: int = 150,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate AggregateRating JSON-LD schema (within Product).

    Args:
        solution_name: Product/solution name
        rating: Average rating (1-5)
        review_count: Number of reviews
        base_url: Optional custom base URL

    Returns:
        JSON-LD Product with AggregateRating schema dict
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": solution_name,
        "description": f"{solution_name} - Trusted by thousands of users",
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": str(min(max(rating, 1.0), 5.0)),
            "bestRating": "5",
            "worstRating": "1",
            "ratingCount": str(max(review_count, 1)),
        },
        "url": url,
    }


def generate_howto_schema(
    solution_name: str,
    niche: str,
    steps: Optional[list[str]] = None,
) -> dict:
    """
    Generate HowTo JSON-LD schema.

    Args:
        solution_name: Solution name for context
        niche: Market niche for context
        steps: Optional list of step descriptions

    Returns:
        JSON-LD HowTo schema dict
    """
    default_steps = [
        f"Sign up for {solution_name}",
        "Complete your profile setup",
        f"Start exploring {niche} features",
        "Connect with your first resources",
        "Begin tracking your progress",
    ]
    step_list = steps or default_steps
    step_list = step_list[:6]  # Max 6 steps for readability

    howto_steps = []
    for i, step in enumerate(step_list, 1):
        howto_steps.append({
            "@type": "HowToStep",
            "position": i,
            "name": f"Step {i}",
            "text": step,
        })

    return {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": f"How to Get Started with {solution_name}",
        "description": f"Quick guide to using {solution_name} for {niche}",
        "step": howto_steps,
    }


def generate_website_schema(
    solution_name: str,
    description: str,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate WebSite JSON-LD schema with SearchAction for sitelinks search box.

    Args:
        solution_name: Name of the solution/website
        description: Site description
        base_url: Optional custom base URL

    Returns:
        JSON-LD WebSite schema dict
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": solution_name,
        "url": url,
        "description": description[:200] if description else solution_name,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{url}/search?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def generate_localbusiness_schema(
    solution_name: str,
    description: str,
    niche: str,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate LocalBusiness JSON-LD schema.

    Args:
        solution_name: Name of the business
        description: Business description
        niche: Market niche for business type
        base_url: Optional custom base URL

    Returns:
        JSON-LD LocalBusiness schema dict
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"
    return {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": solution_name,
        "url": url,
        "description": description[:200] if description else solution_name,
        "address": {
            "@type": "PostalAddress",
            "addressCountry": "US",
        },
        "priceRange": "$$",
        "image": f"{url}/assets/logo.png",
    }


def generate_dataset_schema(
    solution_name: str,
    description: str,
    niche: str,
    base_url: Optional[str] = None,
) -> dict:
    """
    Generate Dataset JSON-LD schema for data-driven solutions.

    Args:
        solution_name: Name of the dataset/solution
        description: Dataset description
        niche: Market niche for context
        base_url: Optional custom base URL

    Returns:
        JSON-LD Dataset schema dict
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{solution_name} Data",
        "description": description[:300] if description else f"{niche} data from {solution_name}",
        "url": f"{url}/data",
        "creator": {
            "@type": "Organization",
            "name": solution_name,
            "url": url,
        },
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }


def generate_json_ld_schemas(
    schema_selections: list["SchemaSelectionLight"],
    solution_name: str,
    value_proposition: str,
    niche: str,
    pricing: Optional[dict] = None,
    base_url: Optional[str] = None,
) -> list[dict]:
    """
    Generate JSON-LD schemas from lightweight LLM selections.

    This is the main entry point for JSON-LD generation.
    Takes LLM schema type selections and generates actual JSON-LD code.

    Args:
        schema_selections: LLM's schema type selections with rationale
        solution_name: Solution name for branding
        value_proposition: Description text for schema content
        niche: Market niche for context
        pricing: Optional pricing info dict
        base_url: Optional custom base URL

    Returns:
        List of dicts compatible with SchemaExample model:
        [{"schema_type": str, "json_ld_code": str}, ...]
    """
    url = base_url or f"https://{_slugify(solution_name)}.com"

    # Map schema types to generator functions
    generators = {
        "Organization": lambda sel: generate_organization_schema(
            solution_name, value_proposition, url
        ),
        "Service": lambda sel: generate_service_schema(
            solution_name, value_proposition, pricing, url
        ),
        "FAQPage": lambda sel: generate_faq_schema(
            sel.suggested_questions or [
                f"What is {solution_name}?",
                f"How does {solution_name} work?",
                f"What are the key features?",
            ],
            solution_name,
            niche,
        ),
        "BreadcrumbList": lambda sel: generate_breadcrumb_schema(url),
        "Article": lambda sel: generate_article_schema(
            f"{niche} Guide", value_proposition, url, solution_name
        ),
        "WebPage": lambda sel: generate_webpage_schema(
            solution_name, value_proposition, url
        ),
        "Review": lambda sel: generate_review_schema(solution_name, base_url=url),
        "HowTo": lambda sel: generate_howto_schema(
            solution_name, niche, sel.suggested_questions
        ),
        "WebSite": lambda sel: generate_website_schema(
            solution_name, value_proposition, url
        ),
        "LocalBusiness": lambda sel: generate_localbusiness_schema(
            solution_name, value_proposition, niche, url
        ),
        "Dataset": lambda sel: generate_dataset_schema(
            solution_name, value_proposition, niche, url
        ),
    }

    results = []
    generated_types = set()

    for selection in schema_selections:
        schema_type = selection.schema_type

        # Normalize schema type (handle case variations)
        normalized_type = None
        for known_type in generators.keys():
            if known_type.lower() == schema_type.lower():
                normalized_type = known_type
                break

        if normalized_type is None:
            logger.warning(
                f"⚠️ Unknown schema type '{schema_type}' - skipping. "
                f"Known types: {list(generators.keys())}"
            )
            continue

        # Skip duplicates
        if normalized_type in generated_types:
            logger.debug(f"Skipping duplicate schema type: {normalized_type}")
            continue

        try:
            generator = generators[normalized_type]
            schema_dict = generator(selection)
            results.append({
                "schema_type": normalized_type,
                "json_ld_code": json.dumps(schema_dict, indent=2),
            })
            generated_types.add(normalized_type)
            logger.debug(f"✅ Generated {normalized_type} JSON-LD schema")
        except Exception as e:
            logger.error(f"Failed to generate {normalized_type} schema: {e}")

    logger.info(
        f"✅ Generated {len(results)} JSON-LD schemas via Python: "
        f"{list(generated_types)}"
    )

    return results
