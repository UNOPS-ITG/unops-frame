"""The envelope is camelCased; row field ids are not, ever.

This is invariant I7. The failure it guards against is silent and estate-wide:
an alias generator reaching a row's value map rewrites a steward's field id and
does not reliably reverse it, so data is corrupted on write and the symptom is
"my field disappeared" weeks later.
"""

import pytest
from pydantic import ValidationError

from api.schemas.base import RequestSchema, ResponseSchema, RestrictedValue, RowValues


class _Envelope(ResponseSchema):
    blueprint_version: int
    row_id: str


class _Body(RequestSchema):
    display_name: str


class _Page(ResponseSchema):
    blueprint_version: int
    values: RowValues


def test_envelope_serialises_camel_case() -> None:
    dumped = _Envelope(blueprint_version=7, row_id="r1").model_dump(by_alias=True)
    assert dumped == {"blueprintVersion": 7, "rowId": "r1"}


def test_envelope_accepts_either_spelling_inbound() -> None:
    assert _Envelope.model_validate({"blueprintVersion": 7, "rowId": "r1"}).row_id == "r1"
    assert _Envelope.model_validate({"blueprint_version": 7, "row_id": "r1"}).row_id == "r1"


def test_request_rejects_unknown_keys() -> None:
    # A typo must be a 422, not a silently ignored write.
    with pytest.raises(ValidationError):
        _Body.model_validate({"displayName": "ok", "dispalyName": "typo"})


@pytest.mark.parametrize(
    "field_id",
    [
        "vendor_name",
        "risk_type",
        "amount",
        "created_at",
        "UPPER_SNAKE",
        "already_camelCase",
        "with-dash",
        "with space",
        "unicode_señor",
        "_leading_underscore",
        "trailing_",
        "n0_digits_1",
    ],
)
def test_row_field_ids_survive_a_round_trip_untouched(field_id: str) -> None:
    values = RowValues(root={field_id: "value"})
    assert values.model_dump(by_alias=True) == {field_id: "value"}
    assert RowValues.model_validate({field_id: "value"}).root == {field_id: "value"}


def test_field_ids_are_untouched_even_inside_a_camelcased_envelope() -> None:
    """The dangerous case: the envelope IS transformed, so the exemption has to
    survive nesting rather than only working on a bare RowValues."""
    page = _Page(blueprint_version=7, values=RowValues(root={"vendor_name": "Acme", "risk_type": "conduct"}))
    dumped = page.model_dump(by_alias=True)

    assert dumped["blueprintVersion"] == 7, "envelope should be camelCased"
    assert dumped["values"] == {"vendor_name": "Acme", "risk_type": "conduct"}
    assert "vendorName" not in dumped["values"]
    assert "riskType" not in dumped["values"]


def test_restricted_stub_is_a_present_key_with_a_discriminator() -> None:
    """PM-5: the field exists, its value does not. Never an absent key, never a
    type default — renderers must not have to branch on key existence."""
    values = RowValues(root={"amount": 50000, "owner_rationale": RestrictedValue()})
    dumped = values.model_dump(by_alias=True)

    assert "owner_rationale" in dumped
    assert dumped["owner_rationale"] == {"restricted": True}
    assert dumped["amount"] == 50000
