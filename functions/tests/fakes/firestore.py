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


class FakeCollectionRef:
    def __init__(self, store: FakeFirestore, path: str) -> None:
        self._store = store
        self.path = path

    def document(self, doc_id: str) -> FakeDocumentRef:
        return FakeDocumentRef(self._store, f"{self.path}/{doc_id}")

    def stream(self) -> list[FakeSnapshot]:
        depth = self.path.count("/") + 2
        return [
            FakeSnapshot(p, d)
            for p, d in sorted(self._store.docs.items())
            if p.startswith(self.path + "/") and p.count("/") + 1 == depth
        ]


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
