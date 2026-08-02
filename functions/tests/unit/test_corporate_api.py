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
    store.seed(
        f"workspaces/{WS}/corporateCatalogue/current",
        {
            "source": {"id": "datahub", "project": "unops-datahub"},
            "dictionary": fixture("dictionary"),
            "tables": fixture("tables"),
            "relations": fixture("relations"),
        },
    )
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

    assert body
    assert all(d["bindable"] for d in body)
    assert all(d["businessKey"] for d in body)


def test_an_unbindable_dimension_is_hidden_by_default_and_says_why_when_shown(
    author: TestClient,
) -> None:
    """A list containing things that cannot be picked is a list where every
    author eventually tries one."""
    shown = author.get(f"{BASE}/dimensions?bindableOnly=false").json()
    hidden = author.get(f"{BASE}/dimensions").json()

    assert len(shown) > len(hidden)
    unbindable = [d for d in shown if not d["bindable"]]
    assert unbindable
    assert all(d["reasons"] for d in unbindable)


def test_an_unclassified_relation_is_not_public(author: TestClient) -> None:
    """Until the probe has run, nothing is open. An unclassified relation is not
    a public one, and that default is what stops a sweep that has not finished
    from disclosing anything."""
    body = author.get(f"{BASE}/dimensions").json()
    assert all(d["disclosure"] == "entitled" for d in body)
    assert all(d["reasons"] for d in body)


def test_a_dimensions_restricted_attributes_are_marked(author: TestClient) -> None:
    """So an author picking attributes to carry onto a row can see which ones
    will make the whole binding entitled."""
    dimensions = author.get(f"{BASE}/dimensions?bindableOnly=false").json()
    with_restricted = [d for d in dimensions if any(a["restricted"] for a in d["attributes"])]

    assert with_restricted, "the fixture should contain a policy-tagged dimension"
    assert any(a["isBusinessKey"] for d in dimensions for a in d["attributes"])


def test_a_fact_reports_the_grain_it_is_keyed_by(author: TestClient) -> None:
    """A Frame row can bind to it only where the row already references every
    dimension in the grain — otherwise there is no defensible answer to which
    rows the number belongs to."""
    facts = author.get(f"{BASE}/facts").json()
    assert facts
    for fact in facts:
        assert fact["grain"]
        assert fact["measures"]


def test_an_unknown_dimension_is_a_404(author: TestClient) -> None:
    assert author.get(f"{BASE}/dimensions/Dimensions_Api.Nope").status_code == 404


def test_an_empty_catalogue_is_an_empty_list_not_an_error(
    author: TestClient, db: FakeFirestore
) -> None:
    """A workspace with no source registered has no corporate data. That is a
    state, not a failure."""
    db.docs.pop(f"workspaces/{WS}/corporateCatalogue/current", None)
    assert author.get(f"{BASE}/dimensions").json() == []


# --- what does not exist --------------------------------------------------


def test_there_is_no_endpoint_that_runs_sql(author: TestClient) -> None:
    """Frame emits four fixed templates and nothing else. An endpoint that
    accepted a query would make that fence unenforceable in one line."""
    from api import create_app  # noqa: F401

    paths = [r.path for r in author.app.routes if hasattr(r, "path")]  # type: ignore[attr-defined]
    for path in paths:
        assert "sql" not in path.lower()
        assert "/query" not in path or "/rows/query" in path
