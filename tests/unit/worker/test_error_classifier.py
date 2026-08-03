import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from worker.error_classifier import classify_error


def test_openrouter_402_is_provider_billing_not_internal_error():
    classified = classify_error(
        "HTTP 402: This request requires more credits, or fewer max_tokens.",
        error_stage=5,
    )

    assert classified.code == "PROVIDER_BILLING_ERROR"
    assert classified.stage == 5


def test_product_credit_wording_without_provider_402_is_not_misclassified():
    classified = classify_error("Insufficient credits to add another idea batch", error_stage=5)

    assert classified.code == "INTERNAL_ERROR"
