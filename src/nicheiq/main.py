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


def run_research(
    niche_description: str,
    allowed_project_types=None,
    resume: bool = False,
    checkpoint_path: str = None
) -> str:
    """
    Run the complete NicheIQ research pipeline.

    Args:
        niche_description: Description of the niche/market to research
        allowed_project_types: Optional list of allowed project types
        resume: If True, automatically resume from latest checkpoint
        checkpoint_path: Explicit checkpoint folder path to resume from

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

    # Initialize research flow
    flow = ResearchFlow(niche_description=niche_description, allowed_project_types=allowed_project_types)

    # Handle checkpoint resume
    if checkpoint_path:
        logger.info(f"Attempting to resume from checkpoint: {checkpoint_path}")
        checkpoint = Path(checkpoint_path)
        if not checkpoint.exists():
            logger.error(f"Checkpoint not found: {checkpoint_path}")
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        if flow.resume_from_checkpoint(checkpoint):
            report_path = flow._execute_remaining_stages()
        else:
            logger.warning("Failed to resume from checkpoint, starting fresh")
            report_path = flow.run_with_resume(auto_resume=False)
    elif resume:
        logger.info("Auto-resume enabled - checking for latest checkpoint")
        report_path = flow.run_with_resume(auto_resume=True)
    else:
        report_path = flow.run_with_resume(auto_resume=False)

    return report_path


def list_checkpoints(niche_description: str = None):
    """
    List available checkpoints for a niche (or all checkpoints).

    Args:
        niche_description: Optional niche to filter checkpoints
    """
    setup_logging()

    if not settings.checkpoint_enabled:
        logger.warning("Checkpointing is disabled")
        return

    if not settings.checkpoint_dir.exists():
        logger.info("No checkpoints directory found")
        return

    # Get all checkpoint folders
    checkpoints = sorted(
        settings.checkpoint_dir.glob("checkpoint_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not checkpoints:
        logger.info("No checkpoints found")
        return

    # Filter by niche if specified
    if niche_description:
        niche_slug = "".join(c if c.isalnum() else "_" for c in niche_description[:50]).lower().strip("_")
        checkpoints = [cp for cp in checkpoints if niche_slug in cp.name.lower()]

    logger.info(f"\nFound {len(checkpoints)} checkpoint(s):")
    logger.info("=" * 80)

    for cp in checkpoints:
        metadata_file = cp / "metadata.json"
        if metadata_file.exists():
            import json
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            niche = metadata.get("niche_description", "Unknown")[:60]
            current_stage = metadata.get("current_stage", "?")
            completed = metadata.get("completed_stages", [])
            last_checkpoint = metadata.get("last_checkpoint_at", "Unknown")

            logger.info(f"\n📁 {cp.name}")
            logger.info(f"   Niche: {niche}...")
            logger.info(f"   Current Stage: {current_stage}")
            logger.info(f"   Completed Stages: {', '.join(str(s) for s in completed)}")
            logger.info(f"   Last Checkpoint: {last_checkpoint}")
            logger.info(f"   Path: {cp}")
        else:
            logger.info(f"\n📁 {cp.name} (no metadata)")

    logger.info("\n" + "=" * 80)


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

  # Checkpoint/Resume examples:
  # Auto-resume from latest checkpoint if available
  python -m nicheiq.main --niche "AI tools" --resume

  # Resume from specific checkpoint folder
  python -m nicheiq.main --niche "AI tools" --checkpoint ./output/checkpoints/checkpoint_ai_tools_20250110_143052

  # List all available checkpoints
  python -m nicheiq.main --list-checkpoints

  # List checkpoints for specific niche
  python -m nicheiq.main --niche "AI tools" --list-checkpoints

  # Disable checkpointing for this run
  python -m nicheiq.main --niche "AI tools" --no-checkpoint
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

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Automatically resume from latest checkpoint if available",
    )

    parser.add_argument(
        "--checkpoint",
        type=str,
        help="Path to specific checkpoint folder to resume from",
    )

    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List all available checkpoints for the specified niche (or all if no niche specified)",
    )

    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable checkpointing for this run",
    )

    args = parser.parse_args()

    # Handle --list-checkpoints command
    if args.list_checkpoints:
        niche_filter = args.niche or settings.niche_description
        list_checkpoints(niche_filter)
        sys.exit(0)

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

    if args.no_checkpoint:
        settings.checkpoint_enabled = False

    # Run research
    try:
        report_path = run_research(
            niche_description,
            allowed_project_types,
            resume=args.resume,
            checkpoint_path=args.checkpoint
        )
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
