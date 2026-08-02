"""Wire schema base classes.

The estate convention is snake_case in Python and camelCase on the wire, done
with a pydantic alias generator. Frame keeps that for the **envelope** and
deliberately exempts one thing from it: **row field values**.

Why that exemption is not a detail. A row's values are keyed by *user-defined
field ids* — a steward creates a field called ``vendor_name`` and that string is
their data, not our naming convention. An alias generator applied to the value
map would rewrite it to ``vendorName`` on the way out and, worse, fail to
reverse it reliably on the way back in (``vendor_name``, ``vendorName`` and
``vendor__name`` do not round-trip). The corruption would be silent, would land
in every row in the estate, and would be discovered by a steward asking why
their field disappeared.

So: envelope keys are transformed, value maps pass through untouched. The rule
is enforced by ``RowValues`` below and by tests; there is no situation in which
a field id should be case-transformed.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, RootModel
from pydantic.alias_generators import to_camel


class _WireModel(BaseModel):
    """Shared configuration for anything that crosses the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        # Accept either spelling inbound. Clients send camelCase; our own tests,
        # fixtures and internal callers are more readable in snake_case.
        populate_by_name=True,
        # Always emit camelCase, even when the object was built by field name.
        serialize_by_alias=True,
    )


class RequestSchema(_WireModel):
    """Base for request bodies.

    ``extra='forbid'`` is deliberate: silently dropping an unrecognised key is
    how a client ends up believing it wrote something it did not. A typo in a
    field name should be a 422, not a no-op.
    """

    model_config = ConfigDict(extra="forbid")


class ResponseSchema(_WireModel):
    """Base for response bodies."""


class RowValues(RootModel[dict[str, Any]]):
    """A row's field values: an opaque map keyed by user-defined field ids.

    A ``RootModel`` rather than a ``BaseModel`` precisely so that no alias
    generator can reach the keys. Serialising this emits exactly the keys the
    steward defined.

    Validation of the *values* is not this type's job — that happens on the
    single server-side path against compiled Blueprint metadata (BP-4), which
    is the only place that knows what a field means.
    """

    root: dict[str, Any]

    def __getitem__(self, field_id: str) -> Any:
        return self.root[field_id]

    def get(self, field_id: str, default: Any = None) -> Any:
        return self.root.get(field_id, default)

    def keys(self) -> Any:
        return self.root.keys()

    def items(self) -> Any:
        return self.root.items()

    def __contains__(self, field_id: str) -> bool:
        return field_id in self.root

    def __len__(self) -> int:
        return len(self.root)


class RestrictedValue(ResponseSchema):
    """The typed stub that stands in for a field the viewer may not read.

    Never an absent key and never a type default (PM-5): the field exists, its
    value does not, and every renderer can rely on the key being present so
    none of them branch on key existence. ``restricted`` is always ``True`` —
    it is a discriminator, not a flag to be toggled.
    """

    restricted: bool = True
