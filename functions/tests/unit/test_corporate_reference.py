"""What a row stores when a field points at corporate data.

The governing line, and most of what these tests check: Frame caches no label
that anyone may be denied.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lib.corporate.model import Dimension, Disclosure, RelationStatus
from lib.corporate.reference import (
    STALE_AFTER_DAYS,
    CorporateRef,
    UnresolvableReference,
    from_value,
    make_reference,
    render,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def dimension(**over: object) -> Dimension:
    return Dimension.model_validate({
        "id": "Dimensions_Api.Asset",
        "dataset": "Dimensions_Api",
        "table": "Asset",
        "label": "Assets",
        "business_key": "Asset",
        "disclosure": Disclosure.OPEN,
        "label_visibility": Disclosure.OPEN,
        **over,
    })


OPEN = dimension()
ENTITLED = dimension(disclosure=Disclosure.ENTITLED, label_visibility=Disclosure.ENTITLED)


# --- what gets cached, and what does not ----------------------------------


def test_an_open_dimension_caches_its_label() -> None:
    """This is what makes the feature affordable: the grid filters, sorts,
    exports and generates documents without touching BigQuery."""
    ref = make_reference(OPEN, "A1", "Forklift", catalogue_version=3, now=NOW)

    assert ref.label == "Forklift"
    assert ref.snapshot_at == NOW
    assert ref.catalogue_version == 3


def test_an_entitled_dimension_caches_nothing_even_when_offered_a_label() -> None:
    """Not defensive coding. The caller is the picker, which resolved that label
    in the PICKING user's context; storing it would show it to every later
    reader of the row, none of whom were checked."""
    ref = make_reference(ENTITLED, "A1", "Confidential Asset", catalogue_version=3, now=NOW)

    assert ref.key == "A1"
    assert ref.label is None
    assert ref.snapshot_at is None


def test_a_dimension_with_no_business_key_cannot_be_referenced() -> None:
    """A stored reference with no identity is a value that looks like data and
    is not."""
    with pytest.raises(UnresolvableReference, match="business key"):
        make_reference(dimension(business_key=None), "A1", "x", catalogue_version=1)


def test_a_quarantined_dimension_cannot_be_referenced_anew() -> None:
    """It stops serving new picks immediately. Existing rows keep rendering —
    that is reconciliation's job, not the picker's."""
    with pytest.raises(UnresolvableReference, match="quarantined"):
        make_reference(
            dimension(status=RelationStatus.QUARANTINED), "A1", "x", catalogue_version=1
        )


def test_an_empty_key_is_refused() -> None:
    with pytest.raises(UnresolvableReference, match="key"):
        make_reference(OPEN, "", "x", catalogue_version=1)


# --- what the grid renders ------------------------------------------------


def test_a_fresh_snapshot_renders_as_itself() -> None:
    ref = make_reference(OPEN, "A1", "Forklift", catalogue_version=1, now=NOW)
    assert render(ref, OPEN, now=NOW) == {
        "key": "A1", "label": "Forklift", "state": "snapshot", "stale": False,
    }


def test_an_old_snapshot_renders_with_a_staleness_marker() -> None:
    """A silently old label is worse than a visibly old one — the first time
    anyone notices otherwise is when two reports disagree."""
    old = CorporateRef(
        key="A1", label="Forklift",
        snapshot_at=NOW - timedelta(days=STALE_AFTER_DAYS + 1),
    )
    assert render(old, OPEN, now=NOW)["stale"] is True


def test_a_snapshot_with_no_timestamp_counts_as_stale() -> None:
    """The safe direction. An unstamped label is of unknown age, and unknown
    age is not the same as fresh."""
    assert render(CorporateRef(key="A1", label="Forklift"), OPEN, now=NOW)["stale"] is True


def test_an_entitled_reference_renders_the_readers_own_resolution() -> None:
    ref = make_reference(ENTITLED, "A1", None, catalogue_version=1, now=NOW)
    rendered = render(ref, ENTITLED, resolved_label="Confidential Asset", now=NOW)

    assert rendered["label"] == "Confidential Asset"
    assert rendered["state"] == "resolved"


def test_an_entitled_reference_that_cannot_be_resolved_is_a_restricted_stub() -> None:
    """Not blank, and not the key: the key of an entitled dimension can itself
    disclose — a project code encoding geography discloses as surely as a
    name."""
    ref = make_reference(ENTITLED, "A1", None, catalogue_version=1, now=NOW)
    assert render(ref, ENTITLED, resolved_label=None, now=NOW) == {"restricted": True}


def test_a_quarantined_relation_still_renders_what_is_stored() -> None:
    """Existing rows keep rendering with a marker. Frame does not auto-rewrite
    governed rows from the warehouse: detection is instant, remediation is a
    costed migration, and conflating them changes a total nobody decided to
    change."""
    ref = CorporateRef(key="A1", label="Forklift", snapshot_at=NOW)
    rendered = render(ref, dimension(status=RelationStatus.QUARANTINED), now=NOW)

    assert rendered["state"] == "quarantined"
    assert rendered["label"] == "Forklift"
    assert rendered["stale"] is True


def test_an_orphaned_reference_shows_its_key_rather_than_nothing() -> None:
    """Hiding it would make the row look empty rather than orphaned, and those
    call for different actions."""
    rendered = render(CorporateRef(key="A1"), None)
    assert rendered == {"key": "A1", "label": "A1", "state": "orphaned"}


# --- parsing what is stored ----------------------------------------------


def test_a_bare_key_is_accepted_because_that_is_what_an_import_supplies() -> None:
    """Asking a spreadsheet to contain a four-field object would make import
    unusable for the field type most likely to be imported."""
    ref = from_value("A1")
    assert ref is not None
    assert ref.key == "A1"
    assert ref.label is None


def test_a_full_value_round_trips() -> None:
    original = make_reference(OPEN, "A1", "Forklift", catalogue_version=7, now=NOW)
    parsed = from_value(original.to_value())

    assert parsed == original


def test_an_unparseable_timestamp_degrades_to_unknown_age() -> None:
    """Which renders as stale, not as fresh."""
    ref = from_value({"key": "A1", "label": "x", "snapshotAt": "not a date"})
    assert ref is not None
    assert ref.snapshot_at is None
    assert ref.is_stale(NOW) is True


def test_a_value_with_no_key_is_not_a_reference() -> None:
    assert from_value({"label": "Forklift"}) is None
    assert from_value(None) is None
    assert from_value(42) is None
