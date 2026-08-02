"""Running a corporate-data query.

**In the user's own context.** Every `entitled` read carries the signed-in
user's OAuth credentials, so BigQuery's IAM, row access policies and column
policy tags are the enforcement point and Frame implements none of it. Frame
does not need to know who may see which row; it needs to not be the thing that
decides.

That claim has a precise scope, and overstating it would be worse than not
making it. Frame does not implement the policy. Frame is not "never in
possession of entitled data": non-interactive contexts — the snapshot refresh,
search indexing, scheduled documents — have no user, and each uses a declared
service identity with its own BigQuery grants. BigQuery still enforces, on a
principal whose grants are visible, audited and reviewed.

**Frame's project submits and pays**, so every job carries:

* `maximumBytesBilled` — enforced by BigQuery, which refuses the job rather than
  running it and sending a bill. None of `maximum_bytes_billed`, dry runs, query
  labels or job timeouts appear anywhere in the estate today.
* labels, so the spend line can be attributed per workspace rather than reported
  as one number called "Frame".
* a job timeout, because a query that outlives the request that asked for it is
  pure cost.

**Tokens are cached; refreshing per call is not viable here.** The estate's
`refresh_google_access_token` does a KMS decrypt plus an OAuth round-trip on
every call — fine for Drive metadata, and on a query path it doubles the latency
of the thing it is protecting. This module takes an already-resolved credential
and states the cache contract it expects, rather than reaching for a token store
itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Protocol

from lib.corporate.sql import Query

DEFAULT_TIMEOUT_MS = 30_000
"""A query that outlives the request that asked for it is pure cost: nobody is
waiting for the answer and Frame still pays for it."""


class QueryRefused(RuntimeError):
    """The job was refused before it ran — over budget, or no credential."""


class QueryFailed(RuntimeError):
    """BigQuery rejected or failed the job.

    Distinct from `QueryRefused` because the correct response differs: refused
    means fix the request, failed may mean the user genuinely cannot see the
    table, and conflating them tells someone to raise a ticket about a quota
    when the answer is that they lack a grant.
    """


@dataclass(frozen=True, slots=True)
class Credential:
    """A resolved access token and who it belongs to.

    Carries the subject so an audit entry can name the principal the query ran
    as — which for a user-context read is the whole point. A credential with no
    subject would make the audit trail say "Frame ran a query", which is exactly
    the thing this design is trying not to be true.
    """

    access_token: str
    subject: str
    is_service: bool = False
    """True for the non-interactive contexts. Recorded so a read performed by a
    service identity is never indistinguishable from one performed by a person.
    """


class CredentialSource(Protocol):
    """Where a token comes from. A protocol so the execution path is testable.

    The implementation is the OAuth connector — the user consents once, Frame
    stores a refresh token under envelope encryption, and an access token is
    cached per user with expiry skew. It is deliberately not this module's
    concern: the thing worth testing here is what happens to a query, not how a
    token was obtained.
    """

    def for_user(self, subject: str) -> Credential | None: ...


@dataclass(slots=True)
class JobConfig:
    project: str
    """The BILLING project — Frame's — not the warehouse. The submitting project
    is billed regardless of where the data lives, which is what makes a
    Frame-owned ceiling both possible and necessary."""

    max_bytes_billed: int = 2_000_000_000
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    workspace_id: str | None = None
    surface: str = "lookup"
    dry_run: bool = False

    def labels(self) -> dict[str, str]:
        """Per-workspace attribution.

        Without it the corporate-data spend is one number nobody owns, and the
        first cost review asks which team is responsible for it — a question
        that cannot be answered retrospectively.
        """
        labels = {"app": "frame", "surface": _label(self.surface)}
        if self.workspace_id:
            labels["workspace"] = _label(self.workspace_id)
        return labels


def _label(value: str) -> str:
    """GCP labels: lowercase, digits, dashes and underscores, 63 chars."""
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.lower())
    return cleaned[:63] or "unknown"


@dataclass(slots=True)
class JobRequest:
    """Exactly what will be sent. Assembled and checkable before it is sent."""

    sql: str
    parameters: list[dict[str, Any]]
    config: JobConfig
    credential: Credential

    def to_payload(self) -> dict[str, Any]:
        return {
            "configuration": {
                "dryRun": self.config.dry_run,
                "jobTimeoutMs": str(self.config.timeout_ms),
                "labels": self.config.labels(),
                "query": {
                    "query": self.sql,
                    "useLegacySql": False,
                    "parameterMode": "NAMED",
                    "queryParameters": self.parameters,
                    # A string because the API wants int64 as a string, and
                    # sending a number silently drops the ceiling on large
                    # values — the exact case a ceiling is for.
                    "maximumBytesBilled": str(self.config.max_bytes_billed),
                },
            }
        }


def bind(query: Query, values: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn declared parameter types plus supplied values into the wire form.

    Every parameter the query declares must be supplied. A missing one is
    refused rather than defaulted: BigQuery would reject it anyway, and a
    default here would let `IN UNNEST(@keys)` run against an empty array and
    return nothing — which is indistinguishable from "you may see nothing".
    """
    missing = set(query.parameters) - set(values)
    if missing:
        raise QueryRefused(
            f"missing query parameter(s): {', '.join(sorted(missing))}. An unsupplied "
            "key list would return no rows, which cannot be told apart from a "
            "permission denial."
        )

    out: list[dict[str, Any]] = []
    for name, declared in query.parameters.items():
        value = values[name]
        if declared.startswith("ARRAY<"):
            inner = declared[len("ARRAY<") : -1]
            if not isinstance(value, (list, tuple)):
                raise QueryRefused(f"parameter {name!r} is {declared} but got {type(value).__name__}")
            out.append({
                "name": name,
                "parameterType": {"type": "ARRAY", "arrayType": {"type": inner}},
                "parameterValue": {"arrayValues": [{"value": _wire(v)} for v in value]},
            })
        else:
            out.append({
                "name": name,
                "parameterType": {"type": declared},
                "parameterValue": {"value": _wire(value)},
            })
    return out


def _wire(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def prepare(
    query: Query,
    values: dict[str, Any],
    config: JobConfig,
    credential: Credential | None,
) -> JobRequest:
    """Assemble a job. Pure — nothing is sent.

    Split from the send so the cost controls, the labelling and the parameter
    binding are all testable with no network and no credential. Every one of
    them is a thing that is either present on every job or present on none, and
    "present on most" is the state that produces a surprising invoice.
    """
    if credential is None:
        raise QueryRefused(
            "no BigQuery credential for this principal. Corporate data is read in "
            "the user's own context, so a missing consent is a missing credential "
            "rather than a reason to fall back to a service identity."
        )
    if config.max_bytes_billed <= 0:
        raise QueryRefused("max_bytes_billed must be positive; an unbounded scan is Frame's bill")

    return JobRequest(
        sql=query.sql,
        parameters=bind(query, values),
        config=config,
        credential=credential,
    )


@dataclass(slots=True)
class Result:
    rows: list[dict[str, Any]] = dc_field(default_factory=list)
    bytes_processed: int = 0
    cache_hit: bool = False
    truncated: bool = False
    """The LIMIT was reached. Surfaced rather than hidden: a picker that shows
    the first fifty of nine hundred matches and says so is usable; one that
    shows fifty and implies that is all of them is misleading."""


def rows_from_payload(payload: dict[str, Any]) -> Result:
    """BigQuery's wire shape into plain dicts.

    Typed by the schema BigQuery returns rather than by the catalogue: the
    catalogue can be stale, the response cannot.
    """
    schema = payload.get("schema", {}).get("fields", [])
    names = [f["name"] for f in schema]
    rows = [
        {name: cell.get("v") for name, cell in zip(names, row.get("f", []), strict=False)}
        for row in payload.get("rows", [])
    ]
    total = int(payload.get("totalRows", len(rows)) or 0)

    return Result(
        rows=rows,
        bytes_processed=int(payload.get("totalBytesProcessed", 0) or 0),
        cache_hit=bool(payload.get("cacheHit", False)),
        truncated=total > len(rows),
    )
