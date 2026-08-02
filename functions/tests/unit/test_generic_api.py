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


BANDED = {
    **BLUEPRINT,
    "permissions": [
        {"principals": ["*"], "actions": ["read", "create", "update"],
         "effect": "allow", "max_band": 1},
    ],
}
"""The demo register's shape: a grant that reaches the ordinary fields and stops
below the sensitive one."""


def test_the_blueprint_endpoint_says_which_fields_this_caller_may_write(
    client: TestClient, db: FakeFirestore
) -> None:
    """A label the server computed, so a create form can omit a field nobody
    will ever be allowed to fill rather than offering a dead end.

    It is not a gate and must never become one: the write path still evaluates
    every field on every write, which the next test asserts by ignoring this
    flag entirely.
    """
    # An unbanded grant reaches everything, so everything is writable. Asserted
    # so a bug that returned `false` everywhere could not pass the banded case
    # by accident.
    everything = {f["id"]: f for f in client.get(f"{BASE}").json()["fields"]}
    assert all(f["writable"] for f in everything.values())

    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", BANDED)
    capped = {f["id"]: f for f in client.get(f"{BASE}").json()["fields"]}

    assert capped["title"]["writable"] is True
    # Band 2, above the cap. Never writable on any row, so offering it in a
    # create form is a permanent, unexplained dead end.
    assert capped["rationale"]["writable"] is False


def test_the_writable_flag_is_a_label_and_not_the_enforcement(
    client: TestClient, db: FakeFirestore
) -> None:
    """A client that ignores it is refused exactly as before.

    This is what keeps PM-4 true: the flag exists so a form can be built, and
    the decision that matters is still made in one place on the write path. If
    this ever starts passing because the FLAG blocked the write, the client has
    become a second evaluator.
    """
    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", BANDED)
    _seed_rows(db, 1)

    response = client.patch(f"{BASE}/rows/r0000", json={"values": {"rationale": "mine now"}})

    assert response.status_code == 403
    assert response.json()["fields"] == ["rationale"]
    stored = db.docs[f"workspaces/{WS}/rows/{BP_ID}/items/r0000"]["values"]
    assert stored["rationale"] == "sealed"


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


# --- import and export ---------------------------------------------------


def test_an_import_defaults_to_a_dry_run(client: TestClient, db: FakeFirestore) -> None:
    """An import that reports its failures only after writing half the file is
    one the user cannot safely retry."""
    body = client.post(f"{BASE}/rows/import", json={
        "csv": "Title,Status\nImported one,open\nImported two,closed\n",
    }).json()

    assert body["dryRun"] is True
    assert body["validRows"] == 2
    assert body["writtenRows"] == 0
    assert db.paths_under(f"workspaces/{WS}/rows/{BP_ID}/items/") == []


def test_a_committed_import_writes_rows_through_the_write_path(
    client: TestClient, db: FakeFirestore
) -> None:
    """Same validation, same audit class, same events as a row typed into the
    grid — which is the whole of BP-4's claim."""
    body = client.post(f"{BASE}/rows/import", json={
        "csv": "Title,Status,Amount\nImported one,open,100\nImported two,closed,200\n",
        "dryRun": False,
    }).json()

    assert body["writtenRows"] == 2
    assert len(db.paths_under(f"workspaces/{WS}/rows/{BP_ID}/items/")) == 2
    assert db.one(f"workspaces/{WS}/audit/")["channel"] == "import"
    assert len(db.one("outbox/")["events"]) == 2


def test_nothing_is_written_while_any_row_is_invalid(
    client: TestClient, db: FakeFirestore
) -> None:
    """A partially applied import is the worst outcome: the user cannot tell
    which rows landed, and re-running duplicates the ones that did."""
    body = client.post(f"{BASE}/rows/import", json={
        "csv": "Title,Amount\nFine,100\n,200\n",
        "dryRun": False,
    }).json()

    assert body["writtenRows"] == 0
    assert any(e["code"] == "required" for e in body["errors"])
    assert db.paths_under(f"workspaces/{WS}/rows/{BP_ID}/items/") == []


def test_an_import_reports_columns_it_could_not_match(client: TestClient) -> None:
    body = client.post(f"{BASE}/rows/import", json={
        "csv": "Title,Nonsense\nx,y\n",
    }).json()
    assert body["unmappedColumns"] == ["Nonsense"]


def test_an_export_returns_csv_with_the_annotation_in_a_header(
    client: TestClient, db: FakeFirestore
) -> None:
    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", {
        **BLUEPRINT,
        "permissions": [
            {"principals": ["*"], "actions": ["read", "export"], "effect": "allow",
             "max_band": 0,
             "row_condition": {"type": "binary", "op": "lt",
                               "left": {"type": "field", "id": "amount"},
                               "right": {"type": "literal", "value": 3}}},
        ],
    })
    _seed_rows(db, 5)

    response = client.post(f"{BASE}/rows/export", json={})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["x-frame-rows-visible"] == "3"
    assert response.headers["x-frame-rows-withheld"] == "2"
    # And in the file itself, because a CSV has nowhere else to put it.
    assert "2 further row(s)" in response.text
    # The restricted band exports as withheld, never as blank.
    assert "(withheld)" in response.text


# --- the delta channel ---------------------------------------------------


def test_a_write_is_visible_to_a_subscriber_as_a_delta(
    client: TestClient, db: FakeFirestore
) -> None:
    """The channel is fed by the outbox the writer already fills in the same
    transaction as the row — not by a second publish that can be lost."""
    created = client.post(f"{BASE}/rows", json={"values": {"title": "New"}}).json()

    body = client.post(f"{BASE}/rows/deltas", json={}).json()

    assert [d["rowId"] for d in body["deltas"]] == [created["id"]]
    assert body["deltas"][0]["kind"] == "upsert"
    assert body["deltas"][0]["changedFields"] == ["title"]


def test_a_delta_never_carries_values(client: TestClient) -> None:
    client.post(f"{BASE}/rows", json={"values": {"title": "New"}})
    body = client.post(f"{BASE}/rows/deltas", json={}).json()

    assert set(body["deltas"][0]) == {"kind", "rowId", "changedFields"}


def test_the_watermark_advances_past_envelopes_that_produced_nothing(
    client: TestClient, db: FakeFirestore
) -> None:
    """Advancing only on delivery means a client whose next thousand envelopes
    are all invisible to it re-examines the same thousand forever — the same
    failure the row cursor avoids."""
    client.post(f"{BASE}/rows", json={"values": {"title": "One"}})
    first = client.post(f"{BASE}/rows/deltas", json={}).json()

    # Nothing new since. The watermark must not rewind, and the second poll must
    # not re-report the first write.
    second = client.post(f"{BASE}/rows/deltas", json={"since": first["since"]}).json()

    assert second["deltas"] == []
    assert second["since"] == first["since"]


def test_a_subscriber_is_not_told_about_rows_it_cannot_read(
    client: TestClient, db: FakeFirestore
) -> None:
    """A delta is a statement that a row exists and moved."""
    client.post(f"{BASE}/rows", json={"values": {"title": "Secret", "amount": 500}})

    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", {
        **BLUEPRINT,
        "permissions": [
            {"principals": ["*"], "actions": ["read", "create"], "effect": "allow"},
            {"principals": ["*"], "actions": ["read"], "effect": "deny",
             "row_condition": {"type": "binary", "op": "gte",
                               "left": {"type": "field", "id": "amount"},
                               "right": {"type": "literal", "value": 100}}},
        ],
    })

    body = client.post(f"{BASE}/rows/deltas", json={}).json()
    assert body["deltas"] == []


def test_a_principal_with_no_read_grant_cannot_open_the_channel(
    client: TestClient, db: FakeFirestore
) -> None:
    db.seed(f"workspaces/{WS}/blueprints/{BP_ID}", {
        **BLUEPRINT,
        "permissions": [{"principals": ["someone-else"], "actions": ["read"], "effect": "allow"}],
    })
    assert client.post(f"{BASE}/rows/deltas", json={}).status_code == 403


def test_an_unknown_blueprint_is_a_404_everywhere(client: TestClient) -> None:
    for path in (
        f"{API}/workspaces/{WS}/blueprints/nope",
        f"{API}/workspaces/{WS}/blueprints/nope/rows",
        f"{API}/workspaces/{WS}/blueprints/nope/openapi.json",
    ):
        assert client.get(path).status_code == 404, path
