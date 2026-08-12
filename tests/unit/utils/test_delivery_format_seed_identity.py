from types import SimpleNamespace

from nicheiq.utils.seed_fidelity import (
    changed_seed_identity_fields,
    seed_identity_snapshot,
)


def test_delivery_format_is_part_of_the_seed_identity_lock():
    idea = SimpleNamespace(delivery_format="browser-extension")
    snapshot = seed_identity_snapshot(idea)

    idea.delivery_format = "web-app"

    assert "delivery_format" in changed_seed_identity_fields(snapshot, idea)
