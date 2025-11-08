"""
Main entry point for NicheIQ - Autonomous Market Research Agent.
"""

import sys
from pathlib import Path

import nest_asyncio
from loguru import logger

from .config.settings import settings
from .flows import ResearchFlow


def setup_logging():
    """Configure loguru logging based on settings."""
    # Apply nest_asyncio to allow nested event loops (fixes twitter-api-client integration)
    nest_asyncio.apply()

    logger.remove()  # Remove default handler

    # Console handler with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File handler for detailed logs
    log_dir = Path(settings.output_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "nicheiq_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info("Logging configured successfully")


def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "SERPER_API_KEY": settings.serper_api_key,
        "REDDIT_CLIENT_ID": settings.reddit_client_id,
        "REDDIT_CLIENT_SECRET": settings.reddit_client_secret,
        "DATAFORSEO_LOGIN": settings.dataforseo_login,
        "DATAFORSEO_PASSWORD": settings.dataforseo_password,
    }

    missing = []
    for var_name, var_value in required_vars.items():
        if not var_value or var_value == f"your_{var_name.lower()}_here":
            missing.append(var_name)

    if missing:
        logger.error("Missing required environment variables:")
        for var in missing:
            logger.error(f"  - {var}")
        logger.error("\nPlease set these variables in your .env file")
        logger.error("See .env.example for reference")
        return False

    logger.info("✓ All required environment variables are set")
    return True


def run_research(niche_description: str, allowed_project_types=None) -> str:
    """
    Run the complete NicheIQ research pipeline.

    Args:
        niche_description: Description of the niche/market to research
        allowed_project_types: Optional list of allowed project types

    Returns:
        Path to the generated research report
    """
    # Setup logging
    setup_logging()

    logger.info("=" * 80)
    logger.info("NicheIQ - Autonomous Market Research Agent")
    logger.info("=" * 80)

    # Log project type constraints if provided
    if allowed_project_types:
        logger.info(f"Project type constraints: {', '.join(allowed_project_types)}")

    # Validate environment
    if not validate_environment():
        raise EnvironmentError("Environment validation failed. Please check your .env file.")

    # Initialize and run research flow
    flow = ResearchFlow(niche_description=niche_description, allowed_project_types=allowed_project_types)
    report_path = flow.run_research()

    return report_path


def main():
    """
    CLI entry point for NicheIQ.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="NicheIQ - Autonomous Market Research Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with niche description
  python -m nicheiq.main --niche "AI-powered project management for remote teams"

  # Constrain to specific project types
  python -m nicheiq.main --niche "expat relocation services" --project-types directory,aggregator

  # With custom output directory
  python -m nicheiq.main --niche "Developer tools for API testing" --output ./results

  # Using environment variable
  export NICHEIQ_NICHE="SaaS for freelance designers"
  python -m nicheiq.main
        """
    )

    parser.add_argument(
        "--niche",
        type=str,
        help="Niche or market area to research (can also use NICHEIQ_NICHE env var)",
    )

    parser.add_argument(
        "--output",
        type=str,
        help=f"Output directory for reports (default: {settings.output_dir})",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=settings.log_level,
        help=f"Logging level (default: {settings.log_level})",
    )

    parser.add_argument(
        "--project-types",
        type=str,
        help="Comma-separated list of allowed project types: saas,directory,aggregator,comparison-tool,marketplace (e.g., 'directory,aggregator')",
    )

    args = parser.parse_args()

    # Get niche description from args or environment
    niche_description = args.niche or settings.niche_description

    if not niche_description:
        parser.error(
            "Niche description is required. Provide it via --niche argument or NICHEIQ_NICHE environment variable."
        )

    # Parse project types if provided
    allowed_project_types = None
    if args.project_types:
        allowed_project_types = [pt.strip() for pt in args.project_types.split(',')]
        # Validate project types
        valid_types = {'saas', 'directory', 'aggregator', 'comparison-tool', 'marketplace'}
        invalid_types = set(allowed_project_types) - valid_types
        if invalid_types:
            parser.error(
                f"Invalid project type(s): {', '.join(invalid_types)}. "
                f"Valid types are: {', '.join(valid_types)}"
            )

    # Update settings if custom values provided
    if args.output:
        settings.output_dir = args.output

    if args.log_level:
        settings.log_level = args.log_level

    # Run research
    try:
        report_path = run_research(niche_description, allowed_project_types)
        logger.info(f"\n✓ Research completed successfully!")
        logger.info(f"✓ Report saved to: {report_path}")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\n\nResearch interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.exception(f"Research failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
