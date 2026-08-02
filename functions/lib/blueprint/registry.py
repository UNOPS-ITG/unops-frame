"""The field type registry.

Code-first application configuration (PRD 00): it defines how Frame behaves as
an application, so it lives in the repository and is seeded to the environment's
store at deploy. Blueprints are the opposite — user-authored data at every tier,
which never rides a build.

Loaded once and cached. Nothing mutates it at runtime; a type is added by a
pull request, because every type implies a renderer, an editor, a validator, a
store mapping, a replica column type, a search treatment and a merge format,
and one added without all seven fails somewhere the author did not look.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_REGISTRY_FILE = Path(__file__).resolve().parents[2] / "config" / "field_types.json"


@dataclass(frozen=True, slots=True)
class FieldType:
    key: str
    label: str
    storage: str
    enabled: bool
    phase: str
    supports: frozenset[str]
    variants: tuple[str, ...]
    system: bool
    admin_only: bool
    option_attributes: tuple[str, ...]
    render_as: tuple[str, ...]

    def allows(self, prop: str) -> bool:
        return prop in self.supports


@dataclass(frozen=True, slots=True)
class SensitivityBands:
    restricted_threshold: int
    by_band: dict[int, str]

    def is_at_or_above_restricted(self, band: int) -> bool:
        """The one question every downstream rule asks (PM-10, SR-6, NT-9, IN-7)."""
        return band >= self.restricted_threshold


@dataclass(frozen=True, slots=True)
class FieldTypeRegistry:
    version: int
    types: dict[str, FieldType]
    bands: SensitivityBands

    def get(self, key: str) -> FieldType | None:
        return self.types.get(key)

    def enabled_keys(self) -> frozenset[str]:
        return frozenset(k for k, t in self.types.items() if t.enabled)

    def declared_keys(self) -> frozenset[str]:
        """Includes disabled types, so a Blueprint referencing a P2 type gets
        "not available until phase 2" rather than "unknown field type" — a much
        more useful thing to be told."""
        return frozenset(self.types)


def _build(raw: dict[str, Any]) -> FieldTypeRegistry:
    types: dict[str, FieldType] = {}
    for key, spec in raw["types"].items():
        types[key] = FieldType(
            key=key,
            label=spec.get("label", key),
            storage=spec["storage"],
            enabled=bool(spec.get("enabled", False)),
            phase=spec.get("phase", "P3"),
            supports=frozenset(spec.get("supports", ())),
            variants=tuple(spec.get("variants", ())),
            system=bool(spec.get("system", False)),
            admin_only=bool(spec.get("admin_only", False)),
            option_attributes=tuple(spec.get("option_attributes", ())),
            render_as=tuple(spec.get("render_as", ())),
        )

    band_spec = raw["sensitivity_bands"]
    bands = SensitivityBands(
        restricted_threshold=int(band_spec["restricted_threshold"]),
        by_band={int(b["band"]): b["key"] for b in band_spec["bands"]},
    )
    return FieldTypeRegistry(version=int(raw["version"]), types=types, bands=bands)


@lru_cache(maxsize=1)
def get_registry() -> FieldTypeRegistry:
    return _build(json.loads(_REGISTRY_FILE.read_text(encoding="utf-8")))
