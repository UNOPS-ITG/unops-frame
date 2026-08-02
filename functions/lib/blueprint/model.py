"""The Blueprint document.

The metaschema (BP-1), expressed as pydantic models rather than a JSON Schema
file so that one definition validates, documents and types the thing. The
metaschema *version* is independent of the Blueprint's own version so the engine
can migrate old Blueprints forward.

Note what is deliberately reserved rather than absent: ``lifecycle`` exists from
P1 carrying only ``lifecycle_status``, and ``masked`` exists on permission rules
and is always false. Both are shapes that would be brutal to retrofit onto live
rows and free to reserve now.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Tier(StrEnum):
    PERSONAL = "personal"
    TEAM = "team"
    ORGANIZATIONAL = "organizational"


class _Strict(BaseModel):
    """Unknown keys are an error, not something to ignore.

    A Blueprint is authored by a UI, an AI draft and occasionally by hand. A
    silently-dropped key means a steward believes they configured something they
    did not, and the divergence surfaces as "the rule doesn't work".
    """

    model_config = ConfigDict(extra="forbid")


class SelectOption(_Strict):
    key: str
    label: str
    colour: str | None = None
    icon: str | None = None
    order: int = 0


class ValidationRule(_Strict):
    """Declarative only. There is no expression escape hatch here: cross-field
    conditions go through the shared grammar (BP-9) so one language covers
    validation, permissions, automations, form logic and report filters."""

    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    regex: str | None = None
    allowed_values: list[str] | None = None
    condition: dict[str, Any] | None = None  # a shared-grammar AST, never a string


class FieldDef(_Strict):
    # --- identity and type ---
    id: str = Field(description="Stable field id. Renaming the LABEL is a metadata edit; this never changes.")
    label: str
    type: str
    variant: str | None = None
    options: list[SelectOption] | None = None
    target: str | None = None       # reference: the target Blueprint id
    dimension: str | None = None    # corporate_reference: the registry dimension key
    precision: int | None = None

    # --- constraints ---
    required: bool = False
    unique: bool = False
    unique_scope: Literal["blueprint", "workspace"] = "blueprint"
    not_null: bool = False
    set_once: bool = False
    default: Any = None
    validation: ValidationRule | None = None

    # --- write control ---
    read_only: bool = False
    no_copy: bool = False           # excluded when a row is duplicated or amended (BP-24)

    # --- display ---
    hidden: bool = False
    help_text: str | None = None
    placeholder: str | None = None
    width: int | None = None
    translatable: bool = False      # reaches user-authored content a UI string table cannot
    render_as: str | None = None

    # --- conditionality (BP-3a): declared ONCE here, consumed by every renderer,
    #     the API and the import path. Authoring the same thing in the form
    #     builder and again in the layout editor guarantees drift and leaves
    #     conditional requiredness unenforced off the form. ---
    visible_when: dict[str, Any] | None = None
    required_when: dict[str, Any] | None = None
    read_only_when: dict[str, Any] | None = None

    # --- surfacing ---
    in_default_columns: bool = False
    in_filter_bar: bool = False
    searchable: bool = False
    indexed: bool = False

    # --- governance ---
    sensitivity: int = 0
    exportable: bool = True

    # --- formula ---
    expression: dict[str, Any] | None = None   # a shared-grammar AST, never a string
    materialized: bool = True


class ChildCollection(_Strict):
    id: str
    label: str
    blueprint: str
    ordering_field: str | None = None
    max_rows: int = 200
    """Capped, and surfaced in the UI rather than discovered in production.

    A parent-plus-children save is one transaction, and Firestore caps a commit
    at 500 writes. The arithmetic is children + parent + 1 audit entry + 1
    outbox envelope <= 500, so 200 leaves real headroom for a wide child row.
    """


class WorkflowState(_Strict):
    key: str
    label: str
    colour: str | None = None
    lifecycle_status: Literal["draft", "submitted", "cancelled"] | None = None
    """At most one implied lifecycle status (BP-22), so a transition to Approved
    submits the row. BP-26 refuses a machine where any path reaches a submitted
    state from a cancelled one."""


class WorkflowTransition(_Strict):
    from_state: str
    to_state: str
    label: str
    condition: dict[str, Any] | None = None


class PermissionRule(_Strict):
    principals: list[str]
    actions: list[str]
    effect: Literal["allow", "deny"] = "allow"
    row_condition: dict[str, Any] | None = None
    field_ids: list[str] | None = None
    max_band: int | None = None
    strict_attributes: bool = False
    """When false (the default) a condition over an absent value does not match,
    so an allow does not apply and a deny does not fire. When true, absence
    matches for deny and not for allow — fail closed. Specified because the
    reference implementation defaults to fail-OPEN, where a blank restricted
    field makes a row visible to everyone."""

    masked: bool = False
    """PM-6 existence masking. Present and always false until P2, so enabling it
    later is an implementation rather than a signature change."""


class ViewDefaults(_Strict):
    title_field: str | None = None
    subtitle_field: str | None = None
    search_fields: list[str] = Field(default_factory=list)
    default_sort: str | None = None
    default_columns: list[str] = Field(default_factory=list)
    icon: str | None = None
    colour: str | None = None


class ReverseLink(_Strict):
    blueprint: str
    field_id: str
    group: str | None = None


class Lifecycle(_Strict):
    submittable: bool = False
    retention_days: int | None = None
    freeze_on_state: str | None = None


class Naming(_Strict):
    """BP-25. A row's display identifier, separate from its opaque key.

    For an agency whose staff quote record ids in audit findings and emails, the
    identifier is a governance artifact, not a column somebody happened to add.
    """

    rule: Literal["opaque", "by_field", "series"] = "opaque"
    field_id: str | None = None
    series_pattern: str | None = None


class Provenance(_Strict):
    original_author: str | None = None
    contributors: list[str] = Field(default_factory=list)
    forked_from: str | None = None
    ai_assisted_elements: list[str] = Field(default_factory=list)


class Blueprint(_Strict):
    metaschema_version: int = 1
    id: str
    version: int = 1
    name: str
    description: str | None = None
    icon: str | None = None
    tier: Tier = Tier.PERSONAL
    workspace_id: str

    fields: list[FieldDef] = Field(default_factory=list)
    children: list[ChildCollection] = Field(default_factory=list)
    reverse_links: list[ReverseLink] = Field(default_factory=list)

    states: list[WorkflowState] = Field(default_factory=list)
    transitions: list[WorkflowTransition] = Field(default_factory=list)
    permissions: list[PermissionRule] = Field(default_factory=list)

    view_defaults: ViewDefaults = Field(default_factory=ViewDefaults)
    lifecycle: Lifecycle = Field(default_factory=Lifecycle)
    naming: Naming = Field(default_factory=Naming)
    provenance: Provenance = Field(default_factory=Provenance)

    def field(self, field_id: str) -> FieldDef | None:
        return next((f for f in self.fields if f.id == field_id), None)
