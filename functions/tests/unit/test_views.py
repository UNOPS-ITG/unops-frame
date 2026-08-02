"""Saved views, and the Milestone 1 exit criterion.

The last test in this file is the one the milestone is for: two people open the
same saved view from the same URL and legitimately see different rows and
different columns, annotated, with nothing in the view itself deciding access.
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

MAYA = "maya@unops.org"
SAM = "sam@unops.org"

# The subject a bypassed request carries. Prefixed on purpose: PM-7 requires a
# bypassed identity to be distinguishable downstream from a real session.
#
# Everything keyed to a principal — membership, view authorship, audit — keys on
# the SUBJECT, never the email, because an address is mutable and reassignable
# and keying grants on one means a recycled address silently inherits them.
# Seeding memberships under the email instead is a silent no-op: the lookup
# misses, the principal resolves with no groups, and every group-scoped rule
# quietly stops matching.
MAYA_SUBJECT = f"dev-bypass:{MAYA}"
SAM_SUBJECT = f"dev-bypass:{SAM}"

BLUEPRINT: dict[str, Any] = {
    "id": BP_ID,
    "name": "Risks",
    "workspace_id": WS,
    "tier": "team",
    "version": 2,
    "view_defaults": {"title_field": "title"},
    "fields": [
        {"id": "title", "label": "Title", "type": "text", "variant": "single",
         "required": True, "indexed": True},
        {"id": "region", "label": "Region", "type": "single_select", "indexed": True,
         "options": [{"key": "emea", "label": "EMEA"}, {"key": "apac", "label": "APAC"}]},
        {"id": "amount", "label": "Amount", "type": "number", "variant": "decimal",
         "indexed": True},
        {"id": "notes", "label": "Notes", "type": "text", "variant": "long"},
        {"id": "rationale", "label": "Rationale", "type": "text", "variant": "long",
         "sensitivity": 2},
    ],
    # Expressed entirely with ALLOWS that union, not with a deny.
    #
    # A deny beats every allow at every scope — that is the documented
    # precedence and it is right, because a deny is how you express an exclusion
    # nobody may override. It is therefore the wrong tool for "most people see
    # the small exposures": a deny on `*` also denies the risk team, since
    # membership of a broader group is not an escape from a deny that names it.
    "permissions": [
        # Everyone: low-sensitivity fields, small exposures only.
        {"principals": ["*"], "actions": ["read"], "effect": "allow", "max_band": 1,
         "row_condition": {"type": "binary", "op": "lt",
                           "left": {"type": "field", "id": "amount"},
                           "right": {"type": "literal", "value": 1_000_000}}},
        # The risk team: every field, every row.
        {"principals": ["group:risk-team"], "actions": ["read"], "effect": "allow"},
    ],
}

EMEA_FILTER = {
    "type": "binary", "op": "eq",
    "left": {"type": "field", "id": "region"},
    "right": {"type": "literal", "value": "emea"},
}


@pytest.fixture
def db() -> FakeFirestore:
    store = FakeFirestore()
    store.seed(f"workspaces/{WS}/blueprints/{BP_ID}", BLUEPRINT)
    store.seed(f"workspaces/{WS}/members/{MAYA_SUBJECT}", {"groups": ["staff", "risk-team"]})
    store.seed(f"workspaces/{WS}/members/{SAM_SUBJECT}", {"groups": ["staff"]})

    for i in range(12):
        store.seed(
            f"workspaces/{WS}/rows/{BP_ID}/items/r{i:03d}",
            {
                "id": f"r{i:03d}",
                "values": {
                    "title": f"Risk {i}",
                    "region": "emea" if i % 2 == 0 else "apac",
                    # Every third EMEA row is above the deny threshold.
                    "amount": 2_000_000 if i % 6 == 0 else 1_000 * i,
                    "notes": f"note {i}",
                    "rationale": f"sealed {i}",
                },
                "eq": [
                    f"fld_title=Risk {i}",
                    f"fld_region={'emea' if i % 2 == 0 else 'apac'}",
                    f"fld_amount={2_000_000 if i % 6 == 0 else 1_000 * i}",
                ],
                "num0": 2_000_000 if i % 6 == 0 else 1_000 * i,
                "txt0": f"Risk {i}",
                "txt1": "emea" if i % 2 == 0 else "apac",
            },
        )
    return store


def _client(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch, email: str) -> TestClient:
    import lib.firestore

    monkeypatch.setattr(lib.firestore, "get_db", lambda: db)

    from api import create_app
    from lib.blueprint.compile import _cached

    _cached.cache_clear()
    settings = Settings(
        environment=Environment.LOCAL,
        iap_audience="test-audience.apps.googleusercontent.com",
        dev_auth_bypass_secret="test-secret",
        dev_auth_bypass_default_email=email,
        dev_auth_bypass_allowed_emails=[MAYA, SAM],
    )
    client = TestClient(create_app(settings))
    client.headers["X-Dev-Auth-Bypass"] = "test-secret"
    return client


@pytest.fixture
def maya(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with _client(db, monkeypatch, MAYA) as c:
        yield c


@pytest.fixture
def sam(db: FakeFirestore, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with _client(db, monkeypatch, SAM) as c:
        yield c


# --- saving and validating -----------------------------------------------


def test_a_view_saves_with_a_filter_and_a_sort(maya: TestClient) -> None:
    response = maya.post(f"{BASE}/views", json={
        "name": "EMEA risks",
        "scope": "shared",
        "filter": EMEA_FILTER,
        "sort": [{"fieldId": "amount", "direction": "desc"}],
        "columns": [{"fieldId": "title"}, {"fieldId": "amount"}],
    })

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "EMEA risks"
    assert body["isMine"] is True
    assert body["warnings"] == []


def test_a_filter_on_a_removed_field_is_refused_at_save_time(maya: TestClient) -> None:
    """Refused now, while the author is here to fix it. At open time it is an
    empty grid, and an empty grid is indistinguishable from a permission
    denial — users conclude the wrong one."""
    response = maya.post(f"{BASE}/views", json={
        "name": "Broken",
        "filter": {"type": "binary", "op": "eq",
                   "left": {"type": "field", "id": "retired_field"},
                   "right": {"type": "literal", "value": "x"}},
    })

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "unknown_field"


def test_a_filter_that_reads_the_signed_in_user_is_refused(maya: TestClient) -> None:
    """A view is opened by whoever holds the link. A filter reading the acting
    principal makes one saved view a different query per viewer — exactly the
    confusion between a view and a permission this design refuses."""
    response = maya.post(f"{BASE}/views", json={
        "name": "Mine only",
        "filter": {"type": "binary", "op": "eq",
                   "left": {"type": "field", "id": "title"},
                   "right": {"type": "subject", "attribute": "email"}},
    })

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "subject_in_filter"


def test_a_sort_with_no_slot_saves_with_a_warning_rather_than_being_refused(
    maya: TestClient,
) -> None:
    """Legal, user-visible, and caused by a Blueprint-level slot budget the view
    author does not control. Refusing would make one steward's field ordering
    decide whether another can save a view."""
    response = maya.post(f"{BASE}/views", json={
        "name": "By notes",
        "sort": [{"fieldId": "notes"}],
    })

    assert response.status_code == 201
    assert response.json()["warnings"][0]["code"] == "unsortable"


def test_grouping_by_a_restricted_field_warns_about_the_group_header(
    maya: TestClient,
) -> None:
    """A group header carries the value. A reader who may not see the value
    would otherwise receive it in the header."""
    response = maya.post(f"{BASE}/views", json={"name": "By rationale", "groupBy": "rationale"})
    assert response.status_code == 201
    codes = {w["code"] for w in response.json()["warnings"]}
    assert "restricted_grouping" in codes


# --- visibility and ownership --------------------------------------------


def test_a_personal_view_is_not_listed_for_anyone_else(
    maya: TestClient, sam: TestClient
) -> None:
    """Personal view names are written casually — "mine, broken", "for the
    Tuesday call" — and were never meant to be read by a colleague."""
    maya.post(f"{BASE}/views", json={"name": "mine, broken", "scope": "personal"})

    assert [v["name"] for v in sam.get(f"{BASE}/views").json()] == []
    assert [v["name"] for v in maya.get(f"{BASE}/views").json()] == ["mine, broken"]


def test_a_shared_view_is_listed_for_everyone(maya: TestClient, sam: TestClient) -> None:
    maya.post(f"{BASE}/views", json={"name": "EMEA risks", "scope": "shared", "filter": EMEA_FILTER})

    listed = sam.get(f"{BASE}/views").json()
    assert [v["name"] for v in listed] == ["EMEA risks"]
    assert listed[0]["isMine"] is False


def test_only_the_author_may_change_a_shared_view(maya: TestClient, sam: TestClient) -> None:
    view_id = maya.post(f"{BASE}/views", json={"name": "EMEA", "scope": "shared"}).json()["id"]

    response = sam.put(f"{BASE}/views/{view_id}", json={"name": "Renamed", "scope": "shared"})
    assert response.status_code == 403
    assert response.json()["author"] == MAYA_SUBJECT


def test_editing_a_view_does_not_reassign_its_author(maya: TestClient) -> None:
    """Authorship is what PM-11 access review reads; a silent reassignment
    would move responsibility for a view without anyone deciding to."""
    view_id = maya.post(f"{BASE}/views", json={"name": "EMEA", "scope": "shared"}).json()["id"]
    updated = maya.put(f"{BASE}/views/{view_id}", json={"name": "EMEA (revised)", "scope": "shared"})
    assert updated.json()["author"] == MAYA_SUBJECT


def test_setting_a_new_default_demotes_the_old_one(maya: TestClient) -> None:
    """Two defaults would make which one a register opens on depend on document
    ordering — stable enough to look correct in testing, different in
    production."""
    maya.post(f"{BASE}/views", json={"name": "First", "scope": "default"})
    maya.post(f"{BASE}/views", json={"name": "Second", "scope": "default"})

    by_name = {v["name"]: v["scope"] for v in maya.get(f"{BASE}/views").json()}
    assert by_name == {"First": "shared", "Second": "default"}


# --- reading through a view ----------------------------------------------


def test_a_view_applies_its_filter(maya: TestClient) -> None:
    view_id = maya.post(
        f"{BASE}/views", json={"name": "EMEA", "scope": "shared", "filter": EMEA_FILTER}
    ).json()["id"]

    rows = maya.get(f"{BASE}/views/{view_id}/rows").json()["rows"]
    assert rows
    assert all(r["values"]["region"] == "emea" for r in rows)


def test_a_view_grants_nothing(maya: TestClient, sam: TestClient) -> None:
    """The property the whole design rests on. Sam can open Maya's view — and
    still sees only what Sam may see."""
    view_id = maya.post(
        f"{BASE}/views", json={"name": "EMEA", "scope": "shared", "filter": EMEA_FILTER}
    ).json()["id"]

    sam_rows = sam.get(f"{BASE}/views/{view_id}/rows").json()
    assert sam_rows["annotation"]["withheld"] > 0
    for row in sam_rows["rows"]:
        assert row["values"]["rationale"] == {"restricted": True}


def test_a_personal_view_cannot_be_opened_by_its_url(maya: TestClient, sam: TestClient) -> None:
    """404 rather than 403: confirming the view exists tells Sam that Maya has
    a view, and its id."""
    view_id = maya.post(f"{BASE}/views", json={"name": "mine", "scope": "personal"}).json()["id"]
    assert sam.get(f"{BASE}/views/{view_id}/rows").status_code == 404


# --- the Milestone 1 exit criterion --------------------------------------


def test_two_people_one_url_one_view_different_rows_and_columns(
    maya: TestClient, sam: TestClient
) -> None:
    """*The* milestone test.

    Maya (risk team) and Sam (staff) open the same saved view at the same URL.
    Both get a correct answer; the answers differ in rows AND in columns; the
    difference is annotated rather than silent; and nothing about the view
    decided any of it.
    """
    view_id = maya.post(
        f"{BASE}/views",
        json={
            "name": "EMEA exposure",
            "scope": "shared",
            "filter": EMEA_FILTER,
            "sort": [{"fieldId": "amount", "direction": "desc"}],
        },
    ).json()["id"]

    url = f"{BASE}/views/{view_id}/rows"
    mine = maya.get(url).json()
    theirs = sam.get(url).json()

    # Rows: Maya sees the large exposures, Sam does not.
    assert mine["annotation"]["visible"] > theirs["annotation"]["visible"]
    assert theirs["annotation"]["withheld"] > 0
    assert mine["annotation"]["withheld"] == 0

    # Columns: the restricted band is a stub for Sam and a value for Maya.
    assert mine["columnStubs"] == []
    assert theirs["columnStubs"] == ["rationale"]
    assert all(r["values"]["rationale"] != {"restricted": True} for r in mine["rows"])
    assert all(r["values"]["rationale"] == {"restricted": True} for r in theirs["rows"])

    # Both answers are honest about their own completeness.
    assert mine["annotation"]["certainty"] == "exact"
    assert theirs["annotation"]["certainty"] == "exact"

    # And the filter still applied for both — a permission difference is not a
    # licence to return the wrong rows.
    assert all(r["values"]["region"] == "emea" for r in mine["rows"])
    assert all(r["values"]["region"] == "emea" for r in theirs["rows"])
