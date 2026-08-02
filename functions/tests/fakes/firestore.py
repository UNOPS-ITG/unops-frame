"""An in-memory stand-in for the Firestore client.

Exists because ``lib.firestore.run_in_transaction`` has a deliberate test seam:
under a fake the transaction is not a real ``Transaction``, so the body runs
directly and the exact read/guard/write sequence of the single write path is
testable with no emulator and no network.

Deliberately narrow. It models the operations the write path uses — path
navigation, ``get``, ``set`` with and without merge, and a transaction that
buffers writes and discards them if the body raises. It is **not** a Firestore
emulator and must not grow into one: the moment a test needs query semantics,
index behaviour or real contention, it needs the emulator, and a fake that
almost models those is worse than no fake at all.
"""

from __future__ import annotations

import copy
from typing import Any


class FakeSnapshot:
    def __init__(self, path: str, data: dict[str, Any] | None) -> None:
        self._path = path
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    @property
    def id(self) -> str:
        return self._path.rsplit("/", 1)[-1]

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data)


class FakeDocumentRef:
    def __init__(self, store: FakeFirestore, path: str) -> None:
        self._store = store
        self.path = path

    def collection(self, name: str) -> FakeCollectionRef:
        return FakeCollectionRef(self._store, f"{self.path}/{name}")

    def get(self, transaction: Any = None) -> FakeSnapshot:
        self._store.reads.append((self.path, transaction is not None))
        return FakeSnapshot(self.path, self._store.docs.get(self.path))

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        self._store.apply(self.path, data, merge)

    def delete(self) -> None:
        self._store.docs.pop(self.path, None)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeDocumentRef) and other.path == self.path

    def __hash__(self) -> int:
        return hash(self.path)


class FakeQuery:
    """Enough of the query surface for the read path, and no more.

    Implements the operations ``FirestoreRowSource`` actually issues:
    ``array_contains_any``, the range operators, ``order_by``, ``start_after``
    with a value tuple, and ``limit``. It does **not** model index requirements,
    contention or Firestore's one-array-clause-per-query rule — a fake that
    almost modelled those would let a query pass here and fail in production,
    which is why the emulator suite exists alongside this one.
    """

    def __init__(self, store: FakeFirestore, prefix: str, depth: int) -> None:
        self._store = store
        self._prefix = prefix
        self._depth = depth
        self._filters: list[tuple[str, str, Any]] = []
        self._order: list[tuple[str, str]] = []
        self._after: dict[str, Any] | None = None
        self._limit: int | None = None

    def _clone(self) -> FakeQuery:
        q = FakeQuery(self._store, self._prefix, self._depth)
        q._filters = list(self._filters)
        q._order = list(self._order)
        q._after = self._after
        q._limit = self._limit
        return q

    def where(self, path: str, op: str, value: Any) -> FakeQuery:
        q = self._clone()
        q._filters.append((path, op, value))
        return q

    def order_by(self, field: str, direction: str = "ASCENDING") -> FakeQuery:
        # The real client raises on "asc"/"desc". A fake that accepted them
        # would pass every test and 500 on the first real request — which is
        # exactly what it did, once.
        if direction not in {"ASCENDING", "DESCENDING"}:
            raise AssertionError(
                f"Firestore rejects direction {direction!r}; use ASCENDING or DESCENDING"
            )
        q = self._clone()
        q._order.append((field, direction))
        return q

    def start_after(self, position: dict[str, Any]) -> FakeQuery:
        q = self._clone()
        q._after = position
        return q

    def limit(self, count: int) -> FakeQuery:
        q = self._clone()
        q._limit = count
        return q

    def stream(self) -> list[FakeSnapshot]:
        rows = [
            (p, d)
            for p, d in self._store.docs.items()
            if p.startswith(self._prefix + "/") and p.count("/") + 1 == self._depth
        ]
        rows = [(p, d) for p, d in rows if all(_passes(d, f) for f in self._filters)]

        for field, direction in reversed(self._order or [("__name__", "ASCENDING")]):
            rows.sort(
                key=lambda item, f=field: _sort_key(item, f),
                reverse=direction == "DESCENDING",
            )

        if self._after is not None:
            rows = _after(rows, self._after, self._order)
        if self._limit is not None:
            rows = rows[: self._limit]
        return [FakeSnapshot(p, d) for p, d in rows]


def _sort_key(item: tuple[str, dict[str, Any]], field: str) -> Any:
    path, data = item
    if field == "__name__":
        return path.rsplit("/", 1)[-1]
    value = data.get(field)
    # Firestore orders missing values first; a None that compared against a
    # number would raise here and hide the real ordering question.
    return (value is not None, value if value is not None else 0)


def _passes(data: dict[str, Any], clause: tuple[str, str, Any]) -> bool:
    path, op, expected = clause
    actual = data.get(path)
    match op:
        case "array_contains_any":
            return isinstance(actual, list) and bool(set(actual) & set(expected))
        case "==":
            return bool(actual == expected)
        case "<":
            return actual is not None and actual < expected
        case "<=":
            return actual is not None and actual <= expected
        case ">":
            return actual is not None and actual > expected
        case ">=":
            return actual is not None and actual >= expected
        case "in":
            return actual in expected
        case _:
            raise AssertionError(f"the fake does not model operator {op!r}")


def _after(
    rows: list[tuple[str, dict[str, Any]]],
    position: dict[str, Any],
    order: list[tuple[str, str]],
) -> list[tuple[str, dict[str, Any]]]:
    """Resume strictly after the named document.

    Matches on the document id rather than by re-deriving the value tuple, which
    is what Firestore does with a snapshot cursor and is the behaviour the
    reader's tests assume.
    """
    doc_id = position.get("__name__")
    for index, (path, _) in enumerate(rows):
        if path.rsplit("/", 1)[-1] == doc_id:
            return rows[index + 1 :]
    return rows


class FakeCollectionRef:
    def __init__(self, store: FakeFirestore, path: str) -> None:
        self._store = store
        self.path = path

    @property
    def _depth(self) -> int:
        return self.path.count("/") + 2

    def document(self, doc_id: str) -> FakeDocumentRef:
        return FakeDocumentRef(self._store, f"{self.path}/{doc_id}")

    def where(self, path: str, op: str, value: Any) -> FakeQuery:
        return FakeQuery(self._store, self.path, self._depth).where(path, op, value)

    def order_by(self, field: str, direction: str = "ASCENDING") -> FakeQuery:
        return FakeQuery(self._store, self.path, self._depth).order_by(field, direction)

    def limit(self, count: int) -> FakeQuery:
        return FakeQuery(self._store, self.path, self._depth).limit(count)

    def start_after(self, position: dict[str, Any]) -> FakeQuery:
        return FakeQuery(self._store, self.path, self._depth).start_after(position)

    def stream(self) -> list[FakeSnapshot]:
        return FakeQuery(self._store, self.path, self._depth).stream()


class FakeTransaction:
    """Buffers writes; the store applies them only if the body returns.

    A fake that wrote through immediately would let a test pass while the real
    transaction rolled the same write back — which is precisely the property
    these tests exist to check.
    """

    def __init__(self, store: FakeFirestore) -> None:
        self._store = store
        self.pending: list[tuple[str, dict[str, Any], bool]] = []

    def set(self, ref: FakeDocumentRef, data: dict[str, Any], merge: bool = False) -> None:
        self.pending.append((ref.path, copy.deepcopy(data), merge))

    def delete(self, ref: FakeDocumentRef) -> None:
        self.pending.append((ref.path, {}, False))

    def commit(self) -> None:
        for path, data, merge in self.pending:
            self._store.apply(path, data, merge)
        self.pending.clear()


class FakeFirestore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.transactions: list[FakeTransaction] = []
        self.reads: list[tuple[str, bool]] = []
        """(path, was_transactional). A read of the current row that does not
        carry the transaction is a read the write is not protected against."""

    def collection(self, name: str) -> FakeCollectionRef:
        return FakeCollectionRef(self, name)

    def transaction(self) -> FakeTransaction:
        txn = FakeTransaction(self)
        self.transactions.append(txn)
        return txn

    def apply(self, path: str, data: dict[str, Any], merge: bool) -> None:
        if merge and path in self.docs:
            self.docs[path] = {**self.docs[path], **copy.deepcopy(data)}
        else:
            self.docs[path] = copy.deepcopy(data)

    # --- test helpers ---

    def seed(self, path: str, data: dict[str, Any]) -> None:
        self.docs[path] = copy.deepcopy(data)

    def paths_under(self, prefix: str) -> list[str]:
        return sorted(p for p in self.docs if p.startswith(prefix))

    def one(self, prefix: str) -> dict[str, Any]:
        matches = self.paths_under(prefix)
        if len(matches) != 1:
            raise AssertionError(f"expected exactly one document under {prefix}, found {matches}")
        return self.docs[matches[0]]
