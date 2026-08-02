"""The transactional commit — the half of the write path that touches the store.

``prepare_write`` is pure and proven separately. What is left, and what these
tests cover, is the part that can only be wrong in the presence of a store:
that the read happens inside the transaction, that row, audit entry and outbox
envelope land together or not at all, and that nothing lands when the write is
refused.
"""

from __future__ import annotations

from typing import Any

import pytest

from lib.rows.writer import WriteConflict, WriteRejected, write_row
from tests.fakes.firestore import FakeFirestore
from tests.unit.test_write_path import COMPILED, CTX, FULL, LIMITED

ROW = "workspaces/ws1/rows/risk/items/r1"
AUDIT = "workspaces/ws1/audit/"
OUTBOX = "outbox/"


@pytest.fixture
def db() -> FakeFirestore:
    store = FakeFirestore()
    store.seed(
        ROW,
        {
            "id": "r1",
            "values": {"title": "Late filing", "amount": 20_000, "owner_rationale": "sealed"},
            "fieldVersions": {"title": 1, "amount": 1, "owner_rationale": 1},
            "createdBy": "maya",
        },
    )
    return store


def _write(db: FakeFirestore, values: dict[str, Any], **kwargs: Any) -> Any:
    return write_row(
        COMPILED, CTX, row_id="r1", submitted_values=values,
        decision=kwargs.pop("decision", FULL), db=db, **kwargs,
    )


def test_the_row_the_audit_entry_and_the_envelope_commit_together(db: FakeFirestore) -> None:
    """A committed row with no event is a permanently missing search document.
    A committed event with no row is a consumer 404 that retries forever."""
    result = _write(db, {"title": "Updated"})

    assert db.docs[ROW]["values"]["title"] == "Updated"
    assert db.one(AUDIT)["action"] == "row.update"
    assert db.one(OUTBOX)["events"][0]["rowId"] == result.row_id
    assert len(db.transactions) == 1


def test_a_refused_write_leaves_nothing_behind(db: FakeFirestore) -> None:
    """Not "the row is unchanged" — no audit entry and no event either. An
    outbox envelope for a write that never happened would publish a phantom."""
    with pytest.raises(WriteRejected):
        _write(db, {"owner_rationale": "leaked"}, decision=LIMITED)

    assert db.docs[ROW]["values"]["owner_rationale"] == "sealed"
    assert db.paths_under(AUDIT) == []
    assert db.paths_under(OUTBOX) == []


def test_the_current_row_is_read_inside_the_transaction(db: FakeFirestore) -> None:
    """Reading first and then opening a transaction is the version of this
    function that passes every test and loses an edit in production: the version
    stamps the write is judged against would be older than the ones it is
    written against, and the conflict check would pass on stale evidence."""
    _write(db, {"title": "Updated"})

    assert db.reads == [(ROW, True)]
    assert db.docs[ROW]["fieldVersions"]["title"] == 2
    assert db.docs[ROW]["fieldVersions"]["amount"] == 1


def test_a_stale_cell_edit_raises_a_conflict_carrying_the_current_value(db: FakeFirestore) -> None:
    """The client needs the winning value to show what it lost — an error that
    only says "conflict" forces a refetch and a second guess."""
    with pytest.raises(WriteConflict) as exc:
        _write(db, {"title": "Mine"}, submitted_versions={"title": 0})

    assert exc.value.fields == ("title",)
    assert exc.value.current == {"title": "Late filing"}
    assert db.docs[ROW]["values"]["title"] == "Late filing"
    assert db.paths_under(OUTBOX) == []


def test_two_clients_editing_different_cells_both_commit(db: FakeFirestore) -> None:
    """The property GR-8 is about, exercised end to end against the store."""
    _write(db, {"title": "Retitled"}, submitted_versions={"title": 1})
    _write(db, {"amount": 30_000}, submitted_versions={"amount": 1})

    assert db.docs[ROW]["values"] == {
        "title": "Retitled", "amount": 30_000, "owner_rationale": "sealed",
    }
    assert len(db.paths_under(OUTBOX)) == 2


def test_a_create_writes_a_row_under_a_server_generated_id(db: FakeFirestore) -> None:
    result = write_row(
        COMPILED, CTX, row_id=None,
        submitted_values={"title": "New risk", "risk_type": "fraud"},
        decision=FULL, db=db,
    )

    path = f"workspaces/ws1/rows/risk/items/{result.row_id}"
    assert db.docs[path]["values"]["title"] == "New risk"
    assert db.docs[path]["createdBy"] == "maya"
    assert db.one(OUTBOX)["events"][0]["type"] == "frame.row.created"


def test_updating_a_row_that_does_not_exist_is_a_not_found_not_a_create(db: FakeFirestore) -> None:
    """An update that silently creates is how a typo'd id becomes an orphan row
    nobody can find."""
    with pytest.raises(WriteRejected) as exc:
        write_row(COMPILED, CTX, row_id="ghost", submitted_values={"title": "x"},
                  decision=FULL, db=db)
    assert exc.value.code == "not_found"
    assert db.paths_under("workspaces/ws1/rows/risk/items/ghost") == []


def test_the_stored_row_keeps_fields_this_write_did_not_send(db: FakeFirestore) -> None:
    """merge=True plus restore-before-validate. Either alone would be enough
    today; both are here because a future caller will forget one."""
    _write(db, {"title": "Updated"}, decision=LIMITED)
    assert db.docs[ROW]["values"]["owner_rationale"] == "sealed"
    assert db.docs[ROW]["values"]["amount"] == 20_000


def test_the_audit_entry_records_the_channel_and_a_trimmable_delta(db: FakeFirestore) -> None:
    _write(db, {"title": "Updated"})
    entry = db.one(AUDIT)

    assert entry["channel"] == "grid"
    assert entry["class"] == "change"
    assert entry["deltas"] == [
        {"fieldId": "title", "before": "Late filing", "after": "Updated"}
    ]


def test_the_envelope_is_written_unpublished(db: FakeFirestore) -> None:
    """The relay flips it. Writing it published would mean a crash between
    commit and publish loses the event with no way to detect the loss."""
    _write(db, {"title": "Updated"})
    assert db.one(OUTBOX)["published"] is False


def test_a_body_that_raises_after_writing_discards_every_write(db: FakeFirestore) -> None:
    """Tested at the seam rather than through ``write_row``, deliberately.

    Today nothing in ``write_row`` can fail after the first ``txn.set``, so
    routing this through the public path would assert a property the code
    cannot currently violate — a test that passes for the wrong reason. The
    moment a child write, a counter increment or a corporate-data snapshot lands
    between those sets, atomicity becomes live, and this test is what will
    already be guarding it.
    """
    from lib.firestore import run_in_transaction
    from lib.paths import audit_entry, outbox_envelope

    def body(txn: Any) -> None:
        txn.set(audit_entry(db, "ws1", "a1"), {"action": "row.update"})
        txn.set(outbox_envelope(db, "e1"), {"published": False})
        raise RuntimeError("a later step failed")

    with pytest.raises(RuntimeError):
        run_in_transaction(body, db=db)

    assert db.paths_under(AUDIT) == []
    assert db.paths_under(OUTBOX) == []
