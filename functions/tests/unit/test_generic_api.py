"""The generated API, end to end.

The claim under test is "zero per-Blueprint code": the same router serves a
register nobody wrote a line of code for. So these tests define a Blueprint at
runtime, put it in the store, and drive the real HTTP surface against it.

They run against the fake Firestore rather than the emulator. That is a
deliberate split — the store translation (order clauses, cursor tuples, index
use) is the emulator's job to verify; what these tests are for is the wiring:
that the route reaches the right library, that a refusal becomes the right
status, and that the wire contract holds.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.core.config import Environment, Settings
from tests.fakes.firestore import FakeFirestore

WS = "ws1"
BP_ID = "risk"
API = "/api/v1"
BASE = f"{API}/workspaces/{WS}/blueprints/{BP_ID}"

BLUEPRINT: dict[str, Any] = {
    "id": BP_ID,
    "name": "Risks",
    "workspace_id": WS,
    "tier": "team",
    "version": 3,
    "view_defaults": {"title_field": "title"},
    "fields": [
        {"id": "title", "label": "Title", "type": "text", "variant": "single",
         "required": True, "indexed": True},
        {"id": "status", "label": "Status", "type": "single_select", "indexed": True,
         "options": [{"key": "open", "label": "Open"}, {"key": "closed", "label": "Closed"}]},
        {"id": "amount", "label": "Amount", "type": "number", "variant": "decimal",
         "indexed": True, "validation": {"min": 0, "max": 1000000}},
        {"id": "rationale", "label": "Rationale", "type": "text", "variant": "long",
         "sensitivity": 2},
    ],
    "permissions": [
        {"principals": ["*"], "actions": ["read", "create", "update"], "effect": "allow"},
    ],
}


@pytest.fixture
def db() -> FakeFirestore:
    store = FakeFirestore()
    store.seed(f"workspaces/{WS}/blueprints/{BP_ID}", BLUEPRINT)
    store.seed(
        f"workspaces/{WS}/members/dev@unops.org",
        {"groups": ["staff"], "roles": ["editor"]},
    )
    return store


@pytest.fixture
def client(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A real app over a fake store.

    ``get_db`` is patched rather than the routers, so the request travels the
    whole real path — middleware, dependencies, permission library, writer —
    and only the store is substituted.
    """
    import lib.firestore

    monkeypatch.setattr(lib.firestore, "get_db", lambda: db)

    from api import create_app
    from api.routers.docs import _document
    from lib.blueprint.compile import _cached

    # Compilation and the OpenAPI document are both cached on the serialised
    # Blueprint, which is right in production and leaks between tests here.
    _cached.cache_clear()
    _document.cache_clear()

    settings = Settings(
        environment=Environment.LOCAL,
        iap_audience="test-audience.apps.googleusercontent.com",
        dev_auth_bypass_secret="test-secret",
        dev_auth_bypass_default_email="dev@unops.org",
        dev_auth_bypass_allowed_emails=["dev@unops.org"],
    )
    with TestClient(create_app(settings)) as c:
        c.headers["X-Dev-Auth-Bypass"] = "test-secret"
        yield c


def _seed_rows(db: FakeFirestore, n: int, *, start: int = 0) -> None:
    for i in range(start, start + n):
        db.seed(
            f"workspaces/{WS}/rows/{BP_ID}/items/r{i:04d}",
            {
                "id": f"r{i:04d}",
                "values": {"title": f"Risk {i}", "status": "open", "amount": i,
                           "rationale": "sealed"},
                "fieldVersions": {"title": 1, "amount": 1},
            },
        )


# --- zero per-Blueprint code ---------------------------------------------


def test_a_blueprint_nobody_wrote_code_for_is_immediately_servable(
    client: TestClient, db: FakeFirestore
) -> None:
    """The whole claim, in one assertion. No router file, no model, no
    migration — a document in the store and the endpoints exist."""
    _seed_rows(db, 3)
    response = client.get(f"{BASE}/rows")

    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 3
    assert body["blueprintId"] == BP_ID
    assert body["blueprintVersion"] == 3


def test_the_row_page_carries_its_annotation_and_count_discriminator(
    client: TestClient, db: FakeFirestore
) -> None:
    """Present from the first response, because adding either later is a
    breaking change to every client that parsed the page."""
    _seed_rows(db, 3)
    body = client.get(f"{BASE}/rows").json()

    assert body["annotation"] == {
        "visible": 3, "withheld": 0, "total": 3,
        "scope": "page", "certainty": "exact", "ceiling": None,
    }


def test_field_ids_are_never_case_transformed_on_the_wire(
    client: TestClient, db: FakeFirestore
) -> None:
    """A steward's field called ``owner_rationale`` is their data, not our
    naming convention. An alias generator reaching the value map would rewrite
    it outbound and fail to reverse it reliably inbound."""
    db.seed(
        f"workspaces/{WS}/rows/{BP_ID}/items/r1",
        {"id": "r1", "values": {"title": "x", "status": "open"}},
    )
    body = client.get(f"{BASE}/rows").json()

    values = body["rows"][0]["values"]
    assert "title" in values
    # The envelope IS camelCased, and the two live side by side in one response.
    assert "fieldVersions" in body["rows"][0]
    assert "hasMore" in body


# --- permissions on the real path ----------------------------------------


def test_a_restricted_field_arrives_as_a_stub_not_an_absent_key(
    client: TestClient, db: FakeFirestore
) -> None:
    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", {
        **BLUEPRINT,
        "permissions": [{"principals": ["*"], "actions": ["read"], "effect": "allow",
                         "max_band": 0}],
    })
    _seed_rows(db, 2)

    body = client.get(f"{BASE}/rows").json()

    assert body["rows"][0]["values"]["rationale"] == {"restricted": True}
    assert body["columnStubs"] == ["rationale"]


def test_a_withheld_row_is_absent_from_the_array_and_present_in_the_count(
    client: TestClient, db: FakeFirestore
) -> None:
    """Never a phantom spacer row. Rows-absent and rows-present-but-blank are
    different virtualization and pagination contracts and cannot be swapped."""
    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", {
        **BLUEPRINT,
        "permissions": [
            {"principals": ["*"], "actions": ["read"], "effect": "allow"},
            {"principals": ["*"], "actions": ["read"], "effect": "deny",
             "row_condition": {"type": "binary", "op": "gte",
                               "left": {"type": "field", "id": "amount"},
                               "right": {"type": "literal", "value": 2}}},
        ],
    })
    _seed_rows(db, 5)

    body = client.get(f"{BASE}/rows").json()

    assert len(body["rows"]) == 2
    assert body["annotation"]["withheld"] == 3
    assert body["annotation"]["total"] == 5


def test_a_row_the_caller_cannot_read_is_a_404_not_a_403(
    client: TestClient, db: FakeFirestore
) -> None:
    """A 403 confirms the row exists, which is a disclosure of its own on a
    register whose row set is itself sensitive."""
    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", {
        **BLUEPRINT,
        "permissions": [{"principals": ["nobody"], "actions": ["read"], "effect": "allow"}],
    })
    _seed_rows(db, 1)

    assert client.get(f"{BASE}/rows/r0000").status_code == 404


def test_an_unauthenticated_request_is_refused(db: FakeFirestore, monkeypatch: Any) -> None:
    """Authentication is applied at include time, not per route: one missed
    decorator on a generated route is a silently public endpoint."""
    import lib.firestore

    monkeypatch.setattr(lib.firestore, "get_db", lambda: db)
    from api import create_app

    settings = Settings(
        environment=Environment.LOCAL,
        iap_audience="test-audience.apps.googleusercontent.com",
    )
    with TestClient(create_app(settings)) as c:
        assert c.get(f"{BASE}/rows").status_code == 401


# --- writing through the API ---------------------------------------------


def test_a_create_returns_the_written_values_and_a_server_generated_id(
    client: TestClient,
) -> None:
    response = client.post(f"{BASE}/rows", json={"values": {"title": "New", "status": "open"}})

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert len(body["id"]) == 32
    assert body["values"]["title"] == "New"


def test_a_patch_changes_only_the_fields_it_names(
    client: TestClient, db: FakeFirestore
) -> None:
    _seed_rows(db, 1)
    response = client.patch(f"{BASE}/rows/r0000", json={"values": {"title": "Renamed"}})

    assert response.status_code == 200
    assert response.json()["changedFields"] == ["title"]
    stored = db.docs[f"workspaces/{WS}/rows/{BP_ID}/items/r0000"]["values"]
    assert stored == {"title": "Renamed", "status": "open", "amount": 0, "rationale": "sealed"}


def test_a_stale_cell_edit_is_a_412_carrying_what_won(
    client: TestClient, db: FakeFirestore
) -> None:
    """412 rather than 409: the client stated a precondition — the version it
    read — and that precondition failed. A 409 invites a blind retry, which
    would overwrite the winner."""
    _seed_rows(db, 1)
    response = client.patch(
        f"{BASE}/rows/r0000",
        json={"values": {"title": "Mine"}, "fieldVersions": {"title": 0}},
    )

    assert response.status_code == 412
    assert response.json()["fields"] == ["title"]
    assert response.json()["current"] == {"title": "Risk 0"}


def test_a_validation_failure_names_every_offending_field(client: TestClient) -> None:
    """Reporting one error at a time makes a wide form a guessing game."""
    response = client.post(
        f"{BASE}/rows", json={"values": {"amount": 9_999_999, "status": "invented"}}
    )

    assert response.status_code == 400
    codes = {e["code"] for e in response.json()["errors"]}
    assert codes == {"required", "max", "options"}


def test_writing_a_restricted_stub_back_is_refused(
    client: TestClient, db: FakeFirestore
) -> None:
    """The round-trip failure Frappe hit with the same masking mechanism: a
    client reads a stub, posts it back on save, and blanks real data."""
    _seed_rows(db, 1)
    response = client.patch(
        f"{BASE}/rows/r0000", json={"values": {"rationale": {"restricted": True}}}
    )

    assert response.status_code == 403
    assert response.json()["fields"] == ["rationale"]
    assert db.docs[f"workspaces/{WS}/rows/{BP_ID}/items/r0000"]["values"]["rationale"] == "sealed"


def test_an_unknown_field_is_a_400_not_a_silent_drop(client: TestClient) -> None:
    """A typo that no-ops is how a client comes to believe it wrote something
    it did not."""
    response = client.post(
        f"{BASE}/rows", json={"values": {"title": "x", "titel": "typo"}}
    )
    assert response.status_code == 400
    assert any(e["fieldId"] == "titel" for e in response.json()["errors"])


def test_a_write_records_the_declared_channel(
    client: TestClient, db: FakeFirestore
) -> None:
    """"Changed by Maya" and "changed by an import Maya started" are different
    facts a reviewer needs to tell apart (PM-7)."""
    client.post(
        f"{BASE}/rows",
        json={"values": {"title": "Imported"}},
        headers={"X-Frame-Channel": "import"},
    )
    assert db.one(f"workspaces/{WS}/audit/")["channel"] == "import"


def test_an_unrecognised_channel_falls_back_rather_than_being_recorded(
    client: TestClient, db: FakeFirestore
) -> None:
    """A client-declared channel that is written through verbatim is an audit
    field an attacker controls."""
    client.post(
        f"{BASE}/rows",
        json={"values": {"title": "x"}},
        headers={"X-Frame-Channel": "definitely-a-human"},
    )
    assert db.one(f"workspaces/{WS}/audit/")["channel"] == "api"


# --- querying ------------------------------------------------------------


def test_a_query_filter_is_an_ast_not_a_string(client: TestClient, db: FakeFirestore) -> None:
    """A string filter needs a parser on the wire, and a parser on the wire is a
    second grammar that drifts from the one permission rules use — at which
    point a filter and a rule disagree about what ``status = 'open'`` means."""
    _seed_rows(db, 5)
    response = client.post(f"{BASE}/rows/query", json={
        "filter": {"type": "binary", "op": "gte",
                   "left": {"type": "field", "id": "amount"},
                   "right": {"type": "literal", "value": 3}},
        "limit": 10,
    })

    assert response.status_code == 200
    assert response.json()["plan"]["storeFilters"] >= 1


def test_a_malformed_cursor_is_a_400(client: TestClient) -> None:
    response = client.post(f"{BASE}/rows/query", json={"cursor": "!!!not-a-cursor"})
    assert response.status_code == 400


def test_an_unsortable_column_is_reported_in_the_plan(
    client: TestClient, db: FakeFirestore
) -> None:
    """So the UI can grey the sort control rather than offering one that
    silently does nothing."""
    _seed_rows(db, 2)
    body = client.get(f"{BASE}/rows?sort=rationale").json()
    assert body["plan"]["unsortable"] is not None


# --- the metadata surface ------------------------------------------------


def test_the_blueprint_endpoint_reports_what_the_store_can_actually_sort(
    client: TestClient,
) -> None:
    """Not whether the type is orderable — whether a slot was assigned. A client
    that assumes the former renders a sort that does nothing."""
    body = client.get(f"{BASE}").json()
    by_id = {f["id"]: f for f in body["fields"]}

    assert by_id["amount"]["sortable"] is True
    assert by_id["rationale"]["sortable"] is False
    assert by_id["rationale"]["restricted"] is True
    assert body["slotPressure"]["num"] == "1/8"


def test_the_openapi_document_narrows_values_to_the_blueprints_fields(
    client: TestClient,
) -> None:
    """Without this narrowing, "generated from metadata" buys the server
    everything and the caller nothing — they still get dict[str, Any]."""
    doc = client.get(f"{BASE}/openapi.json").json()
    values = doc["components"]["schemas"]["Values"]

    assert set(values["properties"]) == {"title", "status", "amount", "rationale"}
    assert values["properties"]["status"]["enum"] == ["open", "closed"]
    assert values["properties"]["amount"]["type"] == "number"
    assert values["required"] == ["title"]
    assert values["additionalProperties"] is False


def test_a_restricted_field_is_typed_as_value_or_stub(client: TestClient) -> None:
    """A generated client otherwise fails to parse a stub where it was told to
    expect a string."""
    doc = client.get(f"{BASE}/openapi.json").json()
    rationale = doc["components"]["schemas"]["Values"]["properties"]["rationale"]

    assert "oneOf" in rationale
    assert {"$ref": "#/components/schemas/RestrictedValue"} in rationale["oneOf"]


def test_the_openapi_document_is_versioned_with_the_blueprint(client: TestClient) -> None:
    doc = client.get(f"{BASE}/openapi.json").json()
    assert doc["info"]["version"] == "3"


def test_an_unknown_blueprint_is_a_404_everywhere(client: TestClient) -> None:
    for path in (
        f"{API}/workspaces/{WS}/blueprints/nope",
        f"{API}/workspaces/{WS}/blueprints/nope/rows",
        f"{API}/workspaces/{WS}/blueprints/nope/openapi.json",
    ):
        assert client.get(path).status_code == 404, path
