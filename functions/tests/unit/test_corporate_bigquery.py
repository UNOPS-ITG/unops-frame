"""The one module that makes a network call.

Tested with the transport substituted, because what needs checking is the shape
of what Frame sends and what it does with what comes back — not that `urllib`
works.
"""

from __future__ import annotations

from typing import Any

import pytest

from lib.corporate.bigquery import BIGQUERY_API, BigQueryClient, BigQueryMetadataReader
from lib.corporate.executor import Credential, JobConfig, QueryFailed
from lib.corporate.sql import AggregationAttempted, lookup_by_keys

MAYA = Credential(access_token="ya29.token", subject="u1")
CONFIG = JobConfig(project="frame-billing", location="EU", workspace_id="ws-demo", surface="lookup")
QUERY = lookup_by_keys("unops-datahub", "Dimensions_Api", "Asset", "Asset", ["Asset"])


class FakeHttp:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {
            "schema": {"fields": [{"name": "Asset"}]},
            "rows": [{"f": [{"v": "A1"}]}],
            "totalRows": "1",
            "totalBytesProcessed": "2400000",
        }
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def __call__(self, url: str, body: dict[str, Any], token: str) -> dict[str, Any]:
        self.calls.append((url, body, token))
        return self.response


def test_the_job_carries_every_cost_control_to_the_wire() -> None:
    """Assembled by the executor and checked there; asserted again here because
    a client that dropped one on the way out would pass every executor test."""
    http = FakeHttp()
    BigQueryClient(http=http).run(QUERY, {"keys": ["A1"]}, CONFIG, MAYA)

    _, body, token = http.calls[0]
    assert body["maximumBytesBilled"] == "2000000000"
    assert body["timeoutMs"] > 0
    assert body["labels"]["workspace"] == "ws-demo"
    assert token == "ya29.token"


def test_short_query_mode_is_requested_with_a_location() -> None:
    """Roughly halves the ~0.7s an "instant" query otherwise costs, most of
    which is orchestration rather than execution — and on a lookup path the
    orchestration IS the latency."""
    http = FakeHttp()
    BigQueryClient(http=http).run(QUERY, {"keys": ["A1"]}, CONFIG, MAYA)

    assert http.calls[0][1]["location"] == "EU"
    assert http.calls[0][1]["jobCreationMode"] == "JOB_CREATION_OPTIONAL"


def test_short_query_mode_is_omitted_without_a_location() -> None:
    """BigQuery cannot infer a region for a job it may not create, and asking
    for the mode without one fails with "Cannot parse  as CloudRegion" — which
    names neither the missing field nor the feature that required it. Degrading
    to a normal job is slower by a few hundred milliseconds, rather than
    broken."""
    http = FakeHttp()
    config = JobConfig(project="frame-billing", surface="lookup")
    BigQueryClient(http=http).run(QUERY, {"keys": ["A1"]}, config, MAYA)

    assert "jobCreationMode" not in http.calls[0][1]
    assert "location" not in http.calls[0][1]


def test_the_query_is_submitted_to_the_billing_project() -> None:
    """The submitting project is billed regardless of where the data lives,
    which is what makes a Frame-owned ceiling both possible and necessary."""
    http = FakeHttp()
    BigQueryClient(http=http).run(QUERY, {"keys": ["A1"]}, CONFIG, MAYA)
    assert http.calls[0][0] == f"{BIGQUERY_API}/projects/frame-billing/queries"


def test_a_permission_error_is_passed_through_verbatim() -> None:
    """BigQuery telling a user something true about their own access is the one
    message that says what to ask for. Replacing it with "corporate data
    unavailable" hides it."""
    http = FakeHttp({"error": {"message": "Access Denied: Table unops-datahub:Restricted.Pay"}})

    with pytest.raises(QueryFailed, match="Access Denied"):
        BigQueryClient(http=http).run(QUERY, {"keys": ["A1"]}, CONFIG, MAYA)


def test_rows_come_back_as_plain_dicts() -> None:
    result = BigQueryClient(http=FakeHttp()).run(QUERY, {"keys": ["A1"]}, CONFIG, MAYA)
    assert result.rows == [{"Asset": "A1"}]
    assert result.bytes_processed == 2_400_000


def test_a_credential_is_never_sent_anywhere_but_bigquery() -> None:
    """The URL is built from a project id that came off a registered Source, and
    this call carries an access token in a header. A scheme confusion or a
    redirect here would send a user's BigQuery credential somewhere it does not
    belong."""
    client = BigQueryClient()

    for url in [
        "http://evil.example/queries",
        "file:///etc/passwd",
        "https://bigquery.googleapis.com.evil.example/bigquery/v2/projects/p/queries",
    ]:
        with pytest.raises(QueryFailed, match="refusing to send a credential"):
            client._post(url, {}, "ya29.token")


def test_the_metadata_reader_cannot_smuggle_an_aggregate() -> None:
    """It takes a string, so it constructs a Query rather than accepting one —
    otherwise a caller could slip a statement past the aggregation check by
    passing raw SQL."""
    reader = BigQueryMetadataReader(BigQueryClient(http=FakeHttp()))

    with pytest.raises(AggregationAttempted):
        reader.read("SELECT COUNT(*) FROM t", CONFIG, MAYA)


def test_the_metadata_reader_returns_rows() -> None:
    reader = BigQueryMetadataReader(BigQueryClient(http=FakeHttp()))
    assert reader.read("SELECT Asset FROM t", CONFIG, MAYA) == [{"Asset": "A1"}]
