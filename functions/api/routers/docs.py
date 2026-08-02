"""OpenAPI, per Blueprint version.

FastAPI's global ``app.openapi()`` memoises onto ``app.openapi_schema``, which is
why ``create_app`` disables the built-in docs routes: the first schema observed
would freeze for the life of the process, and Frame's endpoint *bodies* change
whenever a steward publishes a Blueprint.

So the document served here is generated per ``(blueprint, version)`` and cached
on that key. A steward publishes a new version, the URL for the new version
returns a new document, and the old version's document keeps describing what it
always described — which is what an integrator who pinned to it needs.

The generic routes in ``rows.py`` accept an opaque value map; this document
narrows it to the Blueprint's actual fields, so a client generator produces a
typed model rather than ``dict[str, Any]``. That narrowing is the whole point:
without it, "the API is generated from metadata" buys the server everything and
the caller nothing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from api.core.exceptions import NotFoundError
from api.dependencies.auth import CurrentUser
from lib.blueprint.compile import CompiledBlueprint
from lib.blueprint.store import BlueprintNotFound, load_compiled

router = APIRouter(tags=["docs"])

_JSON_TYPE = {
    "string": "string",
    "number": "number",
    "boolean": "boolean",
    "timestamp": "string",
    "string_array": "array",
    "corporate_ref": "object",
}


def _db(request: Request) -> Any:
    from lib.firestore import get_db

    return get_db()


Db = Annotated[Any, Depends(_db)]


@router.get("/workspaces/{workspace_id}/blueprints/{blueprint_id}/openapi.json")
def blueprint_openapi(
    workspace_id: str, blueprint_id: str, user: CurrentUser, db: Db
) -> dict[str, Any]:
    try:
        compiled = load_compiled(db, workspace_id, blueprint_id)
    except BlueprintNotFound as exc:
        raise NotFoundError(f"No Blueprint {blueprint_id!r}") from exc

    return _document(compiled.blueprint.model_dump_json(), workspace_id)


@lru_cache(maxsize=256)
def _document(blueprint_json: str, workspace_id: str) -> dict[str, Any]:
    """Cached on the serialised document, like compilation itself.

    Keying on ``(id, version)`` would serve a stale document after an
    unversioned edit in development, and the author's symptom would be "my new
    field is not in the schema" with nothing to point at.
    """
    from lib.blueprint.compile import compile_cached
    from lib.blueprint.model import Blueprint

    compiled = compile_cached(Blueprint.model_validate_json(blueprint_json))
    base = f"/workspaces/{workspace_id}/blueprints/{compiled.id}/rows"

    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"{compiled.blueprint.name} — Frame",
            "version": f"{compiled.version}",
            "description": (
                "Generated from Blueprint metadata. Field-level access is decided "
                "per row per caller, so a field present in this schema may still "
                "return a restricted stub."
            ),
        },
        "paths": {
            base: {
                "get": {
                    "summary": f"List {compiled.blueprint.name}",
                    "responses": {"200": {"description": "A trimmed page"}},
                },
                "post": {
                    "summary": f"Create a {compiled.blueprint.name} row",
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/RowWrite"}}
                        }
                    },
                    "responses": {"201": {"description": "Created"}},
                },
            },
            f"{base}/{{rowId}}": {
                "get": {"responses": {"200": {"description": "One row"}}},
                "patch": {
                    "summary": "Change specific fields",
                    "description": (
                        "Field-scoped. Send only what changed; omitted fields keep "
                        "their stored values, and two callers changing different "
                        "fields of one row both succeed."
                    ),
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/RowWrite"}}
                        }
                    },
                    "responses": {
                        "200": {"description": "Written"},
                        "412": {"description": "A concurrent edit changed the same fields"},
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "Values": _values_schema(compiled),
                "RowWrite": {
                    "type": "object",
                    "required": ["values"],
                    "properties": {
                        "values": {"$ref": "#/components/schemas/Values"},
                        "fieldVersions": {
                            "type": "object",
                            "additionalProperties": {"type": "integer"},
                            "description": (
                                "What you believe you read. Omit to write without "
                                "claiming to know the current state."
                            ),
                        },
                    },
                },
                "RestrictedValue": {
                    "type": "object",
                    "description": (
                        "Stands in for a field you may not read. Always present, "
                        "never an absent key and never a type default."
                    ),
                    "properties": {"restricted": {"const": True}},
                },
            }
        },
    }


def _values_schema(compiled: CompiledBlueprint) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_id, cf in compiled.fields.items():
        definition = cf.definition
        schema: dict[str, Any] = {
            "title": definition.label,
            "type": _JSON_TYPE.get(cf.storage, "string"),
        }
        if cf.storage == "timestamp":
            schema["format"] = "date-time"
        if definition.options:
            schema["enum"] = [o.key for o in definition.options]
        if definition.help_text:
            schema["description"] = definition.help_text
        if definition.read_only:
            schema["readOnly"] = True
        if cf.is_restricted:
            # Declared in the schema, so a generated client has a type for the
            # stub instead of failing to parse a value it was told is a number.
            schema = {
                "oneOf": [schema, {"$ref": "#/components/schemas/RestrictedValue"}],
                "title": definition.label,
            }

        properties[field_id] = schema
        # required_when is deliberately NOT folded in: it is evaluated against
        # the row on the server, and a static schema that claimed it
        # unconditionally would reject valid partial saves before they were sent.
        if definition.required and definition.required_when is None:
            required.append(field_id)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        # Field ids are the steward's data and are never case-transformed on the
        # wire. An alias generator applied here would rewrite vendor_name to
        # vendorName outbound and fail to reverse it reliably inbound.
        "additionalProperties": False,
    }
