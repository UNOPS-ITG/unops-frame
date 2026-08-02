"""The corporate-data API surface.

Three properties dominate: registering a source is a governance action, the
catalogue defaults to safe, and there is no endpoint that runs SQL.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.core.config import Environment, Settings
from tests.fakes.firestore import FakeFirestore

WS = "ws1"
API = "/api/v1"
BASE = f"{API}/workspaces/{WS}/corporate"

ADMIN = "admin@unops.org"
AUTHOR = "author@unops.org"
FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "warehouse"


def fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def db() -> FakeFirestore:
    store = FakeFirestore()
    store.seed(f"workspaces/{WS}/members/dev-bypass:{ADMIN}", {"roles": ["manager"]})
    store.seed(f"workspaces/{WS}/members/dev-bypass:{AUTHOR}", {"roles": ["editor"]})
    # Seeded by running a real sweep and persisting it, rather than by
    # hand-writing documents. A fixture shaped by hand drifts from what the
    # sweep actually writes, and the first symptom is an API test that passes
    # against a shape nothing produces.
    from lib.corporate.executor import Credential
    from lib.corporate.model import Source
    from lib.corporate.sweep_job import persist, run_sweep

    class Reader:
        def read(self, sql: str, config: Any, credential: Any) -> list[dict[str, Any]]:
            if "Datahub_Data_Dictionary" in sql:
                return fixture("dictionary")
            if "Datahub_Table_Reference" in sql:
                return fixture("relations")
            return fixture("tables")

    source = Source(id="datahub", project="unops-datahub")
    catalogue, result = run_sweep(
        source,
        Reader(),
        Credential(access_token="t", subject="sa", is_service=True),
        billing_project="frame-billing",
    )
    persist(store, WS, source, catalogue, result)
    return store


def _client(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch, email: str) -> TestClient:
    import lib.firestore

    monkeypatch.setattr(lib.firestore, "get_db", lambda: db)
    from api import create_app

    settings = Settings(
        environment=Environment.LOCAL,
        iap_audience="test-audience.apps.googleusercontent.com",
        dev_auth_bypass_secret="test-secret",
        dev_auth_bypass_default_email=email,
        dev_auth_bypass_allowed_emails=[ADMIN, AUTHOR],
    )
    client = TestClient(create_app(settings))
    client.headers["X-Dev-Auth-Bypass"] = "test-secret"
    return client


@pytest.fixture
def admin(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with _client(db, monkeypatch, ADMIN) as c:
        yield c


@pytest.fixture
def author(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with _client(db, monkeypatch, AUTHOR) as c:
        yield c


# --- registering a source is a governance action -------------------------


def test_only_a_workspace_manager_may_register_a_source(author: TestClient) -> None:
    """Not because registering is dangerous in itself, but because the project
    named here is the one that receives the invoice."""
    response = author.put(f"{BASE}/sources/datahub", json={
        "id": "datahub", "project": "unops-datahub",
    })
    assert response.status_code == 403


def test_a_manager_registers_a_source_with_only_a_project_and_exclusions(
    admin: TestClient, db: FakeFirestore
) -> None:
    """Deliberately tiny. Anything more would be a registration queue by another
    name — everything else is discovered."""
    response = admin.put(f"{BASE}/sources/datahub", json={
        "id": "datahub",
        "project": "unops-datahub",
        "excludedDatasets": ["Restricted"],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["project"] == "unops-datahub"
    assert body["excludedDatasets"] == ["Restricted"]
    assert body["maxBytesBilled"] > 0


def test_a_source_cannot_be_registered_without_a_spend_ceiling(admin: TestClient) -> None:
    """Frame's own project submits and pays, so an unbounded scan is Frame's
    bill."""
    response = admin.put(f"{BASE}/sources/datahub", json={
        "id": "datahub", "project": "p", "maxBytesBilled": 0,
    })
    assert response.status_code == 400
    assert "bill" in response.json()["detail"]


def test_the_id_in_the_body_must_match_the_url(admin: TestClient) -> None:
    response = admin.put(f"{BASE}/sources/datahub", json={"id": "other", "project": "p"})
    assert response.status_code == 400


# --- the catalogue --------------------------------------------------------


def test_the_catalogue_lists_what_a_blueprint_author_can_bind_to(author: TestClient) -> None:
    body = author.get(f"{BASE}/dimensions").json()

    assert body["items"]
    assert all(d["bindable"] for d in body["items"])
    assert all(d["businessKey"] for d in body["items"])


def test_an_unbindable_dimension_is_hidden_by_default_and_says_why_when_shown(
    author: TestClient,
) -> None:
    """A list containing things that cannot be picked is a list where every
    author eventually tries one."""
    shown = author.get(f"{BASE}/dimensions?bindableOnly=false").json()
    hidden = author.get(f"{BASE}/dimensions").json()

    assert shown["total"] > hidden["total"]
    unbindable = [d for d in shown["items"] if not d["bindable"]]
    assert unbindable
    assert all(d["reasons"] for d in unbindable)


def test_the_catalogue_is_searched_and_paged_on_the_server(author: TestClient) -> None:
    """The real warehouse is 555 dimensions and 388 facts; returning all of them
    with their column lists is 2.1 MB to render a browse page. Both halves of
    the fix are asserted here — the search narrows, and the page states what it
    did not return."""
    everything = author.get(f"{BASE}/dimensions?bindableOnly=false").json()
    label = everything["items"][0]["label"]

    narrowed = author.get(f"{BASE}/dimensions?bindableOnly=false&q={label}").json()
    assert narrowed["matched"] < everything["matched"]
    assert narrowed["total"] == everything["total"], "total is before the search term"

    one = author.get(f"{BASE}/dimensions?bindableOnly=false&limit=1").json()
    assert len(one["items"]) == 1
    # Stated rather than silently truncated: a short list that does not admit it
    # reads as the whole answer.
    assert one["matched"] > 1

    nothing = author.get(f"{BASE}/dimensions?q=nothing-matches-this-xyzzy").json()
    assert nothing["items"] == []
    assert nothing["matched"] == 0


def test_the_list_omits_columns_and_the_detail_endpoint_carries_them(
    author: TestClient,
) -> None:
    """Columns are the bulk of the payload and almost nobody opens a card."""
    listed = author.get(f"{BASE}/dimensions").json()["items"][0]
    assert listed["attributes"] == []

    detail = author.get(f"{BASE}/dimensions/{listed['id']}").json()
    assert detail["attributes"]


def test_an_unclassified_relation_is_not_public(author: TestClient) -> None:
    """Until the probe has run, nothing is open. An unclassified relation is not
    a public one, and that default is what stops a sweep that has not finished
    from disclosing anything."""
    body = author.get(f"{BASE}/dimensions").json()
    assert all(d["disclosure"] == "entitled" for d in body["items"])
    assert all(d["reasons"] for d in body["items"])


def test_a_dimensions_restricted_attributes_are_marked(author: TestClient) -> None:
    """So an author picking attributes to carry onto a row can see which ones
    will make the whole binding entitled."""
    listed = author.get(f"{BASE}/dimensions?bindableOnly=false").json()["items"]
    detailed = [author.get(f"{BASE}/dimensions/{d['id']}").json() for d in listed]
    with_restricted = [d for d in detailed if any(a["restricted"] for a in d["attributes"])]

    assert with_restricted, "the fixture should contain a policy-tagged dimension"
    assert any(a["isBusinessKey"] for d in detailed for a in d["attributes"])


def test_a_fact_reports_the_grain_it_is_keyed_by(author: TestClient) -> None:
    """A Frame row can bind to it only where the row already references every
    dimension in the grain — otherwise there is no defensible answer to which
    rows the number belongs to."""
    facts = author.get(f"{BASE}/facts").json()["items"]
    assert facts
    for fact in facts:
        assert fact["grain"]
        # Measures come from the detail endpoint, like dimension attributes.
        assert author.get(f"{BASE}/facts/{fact['id']}").json()["measures"]


def test_an_unknown_dimension_is_a_404(author: TestClient) -> None:
    assert author.get(f"{BASE}/dimensions/Dimensions_Api.Nope").status_code == 404


def test_an_unknown_fact_is_a_404(author: TestClient) -> None:
    assert author.get(f"{BASE}/facts/Facts_Api.Nope").status_code == 404


def test_an_empty_catalogue_is_an_empty_list_not_an_error(
    author: TestClient, db: FakeFirestore
) -> None:
    """A workspace with no source registered has no corporate data. That is a
    state, not a failure."""
    # The relations, not just the root: the catalogue lives one document per
    # relation, and removing only the root would leave the list populated from
    # a catalogue whose summary is gone.
    for path in db.paths_under(f"workspaces/{WS}/corporateCatalogue/"):
        db.docs.pop(path, None)
    body = author.get(f"{BASE}/dimensions").json()
    assert body["items"] == []
    assert body["total"] == 0


# --- what does not exist --------------------------------------------------


def test_there_is_no_endpoint_that_runs_sql(author: TestClient) -> None:
    """Frame emits four fixed templates and nothing else. An endpoint that
    accepted a query would make that fence unenforceable in one line."""
    from api import create_app  # noqa: F401

    paths = [r.path for r in author.app.routes if hasattr(r, "path")]  # type: ignore[attr-defined]
    for path in paths:
        assert "sql" not in path.lower()
        assert "/query" not in path or "/rows/query" in path
