#!/usr/bin/env python
"""
NicheIQ Setup Validation Script
Checks that your environment is properly configured before running research.
"""

import sys
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_check(passed, message):
    """Print a check result."""
    symbol = "✓" if passed else "✗"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {message}")


def check_python_version():
    """Check Python version is compatible."""
    print_header("Checking Python Version")

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    is_compatible = version.major == 3 and version.minor >= 10

    print_check(is_compatible, f"Python {version_str}")

    if not is_compatible:
        print("  ⚠️  NicheIQ requires Python 3.10 or higher")
        print("  Install from: https://www.python.org/downloads/")

    return is_compatible


def check_dependencies():
    """Check that required packages are installed."""
    print_header("Checking Dependencies")

    required_packages = [
        ("crewai", "CrewAI framework"),
        ("crewai_tools", "CrewAI tools"),
        ("pydantic", "Data validation"),
        ("praw", "Reddit API"),
        ("requests", "HTTP requests"),
        ("loguru", "Logging"),
        ("tenacity", "Retry logic"),
    ]

    all_installed = True

    for package, description in required_packages:
        try:
            __import__(package)
            print_check(True, f"{package:20s} - {description}")
        except ImportError:
            print_check(False, f"{package:20s} - {description} (NOT INSTALLED)")
            all_installed = False

    if not all_installed:
        print("\n  Install missing packages:")
        print("  uv pip install -e .  # or pip install -e .")

    return all_installed


def check_env_file():
    """Check that .env file exists."""
    print_header("Checking Environment File")

    env_path = Path(".env")
    example_path = Path(".env.example")

    exists = env_path.exists()
    print_check(exists, ".env file exists")

    if not exists:
        print("  Create .env file:")
        if example_path.exists():
            print("  cp .env.example .env")
        else:
            print("  Create .env manually")

    return exists


def check_api_keys():
    """Check that API keys are configured."""
    print_header("Checking API Keys")

    try:
        from nicheiq.config.settings import settings
    except Exception as e:
        print_check(False, f"Cannot load settings: {e}")
        return False

    checks = [
        ("OpenAI API Key", settings.openai_api_key, "sk-"),
        ("Serper API Key", settings.serper_api_key, None),
        ("Reddit Client ID", settings.reddit_client_id, None),
        ("Reddit Client Secret", settings.reddit_client_secret, None),
        ("DataForSEO Login", settings.dataforseo_login, None),
        ("DataForSEO Password", settings.dataforseo_password, None),
    ]

    all_configured = True

    for name, value, prefix in checks:
        if not value or "your_" in str(value).lower() or "_here" in str(value).lower():
            print_check(False, f"{name:25s} - NOT CONFIGURED")
            all_configured = False
        elif prefix and not str(value).startswith(prefix):
            print_check(False, f"{name:25s} - INVALID FORMAT (should start with '{prefix}')")
            all_configured = False
        else:
            masked = str(value)[:10] + "..." if len(str(value)) > 10 else "***"
            print_check(True, f"{name:25s} - {masked}")

    # Check optional keys
    print("\n  Optional API Keys:")
    optional_checks = [
        ("Twitter Username", settings.twitter_username),
        ("Twitter Password", settings.twitter_password),
        ("Twitter Email", settings.twitter_email),
    ]

    for name, value in optional_checks:
        if value and "your_" not in str(value).lower():
            masked = str(value)[:10] + "..." if len(str(value)) > 10 else "***"
            print_check(True, f"{name:25s} - {masked}")
        else:
            print(f"  ○ {name:25s} - Not configured (will use guest mode)")

    if not all_configured:
        print("\n  Set missing API keys in .env file")
        print("  See GETTING_STARTED.md for detailed instructions")

    return all_configured


def check_api_connectivity():
    """Test API connectivity (optional, requires API calls)."""
    print_header("Testing API Connectivity (Optional)")

    print("  Skipping live API tests to avoid charges")
    print("  To test APIs, run your first research:")
    print("  python -m nicheiq.main --niche 'test niche'")

    return True


def check_output_directory():
    """Check that output directory is writable."""
    print_header("Checking Output Directory")

    try:
        from nicheiq.config.settings import settings
        output_dir = Path(settings.output_dir)

        # Try to create directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Try to write a test file
        test_file = output_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()

        print_check(True, f"Output directory writable: {output_dir}")
        return True

    except Exception as e:
        print_check(False, f"Cannot write to output directory: {e}")
        print("  Fix with: mkdir -p output && chmod 755 output")
        return False


def main():
    """Run all validation checks."""
    print("\n" + "=" * 80)
    print("  NicheIQ Setup Validation")
    print("=" * 80)

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment File", check_env_file),
        ("API Keys", check_api_keys),
        ("Output Directory", check_output_directory),
        ("API Connectivity", check_api_connectivity),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n  Error during {name} check: {e}")
            results[name] = False

    # Summary
    print_header("Validation Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        print_check(result, name)

    print(f"\n  {passed}/{total} checks passed")

    if passed == total:
        print("\n  ✅ Your environment is ready!")
        print("  Run your first research:")
        print("  python -m nicheiq.main --niche 'AI tools for content creators'")
        return 0
    else:
        print("\n  ⚠️  Some checks failed. Please fix the issues above.")
        print("  See GETTING_STARTED.md for detailed setup instructions:")
        print("  https://github.com/yourusername/nicheiq/blob/main/GETTING_STARTED.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
