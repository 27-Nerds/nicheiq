"""Tests for nicheiq.utils.slugify."""

import pytest

from nicheiq.utils.slugify import slugify


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Hello World", "hello-world"),
        ("Bidirectional Charging (V2H/V2X) Implementation Challenges",
         "bidirectional-charging-v2h-v2x-implementation-challenges"),
        ("Already-Slugified", "already-slugified"),
        ("UPPER CASE", "upper-case"),
        ("trailing--dashes--", "trailing-dashes"),
        ("--leading-dashes", "leading-dashes"),
        ("multiple   spaces", "multiple-spaces"),
        ("punctuation!?!?", "punctuation"),
        ("a/b/c", "a-b-c"),
        ("ev_charging.installation", "ev-charging-installation"),
        ("123-numeric-456", "123-numeric-456"),
    ],
)
def test_slugify_basic(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_slugify_empty() -> None:
    assert slugify("") == ""


def test_slugify_all_punctuation() -> None:
    assert slugify("!@#$%^&*()") == ""


def test_slugify_unicode_strips_to_empty() -> None:
    # Non-ASCII characters are non-alphanumeric in our regex (a-z0-9 only)
    # so they collapse to dashes and strip out.
    assert slugify("café") == "caf"
    assert slugify("日本語") == ""


def test_slugify_idempotent() -> None:
    s = slugify("Hello World!")
    assert slugify(s) == s
