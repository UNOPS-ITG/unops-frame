"""Preparing a corporate-data job.

Everything here is a property that must hold on *every* job. "Present on most
jobs" is the state that produces a surprising invoice and an audit trail that
cannot answer who read what.
"""

from __future__ import annotations

import pytest

from lib.corporate.executor import (
    Credential,
    JobConfig,
    QueryRefused,
    bind,
    prepare,
    rows_from_payload,
)
from lib.corporate.sql import fact_measures_at_grain, lookup_by_keys, search_labels

MAYA = Credential(access_token="ya29.token", subject="u1")
CONFIG = JobConfig(project="frame-billing", workspace_id="ws-demo", surface="lookup")

KEYS_QUERY = lookup_by_keys(
    "unops-datahub", "Dimensions_Api", "Asset", "Asset", ["Asset", "Asset_Description"]
)


# --- the user's own context ----------------------------------------------


def test_no_credential_refuses_rather_than_falling_back() -> None:
    """A missing consent is a missing credential, not a reason to run as a
    service identity. Falling back would make Frame the enforcement point for
    exactly the data this design refuses to be responsible for."""
    with pytest.raises(QueryRefused, match="credential"):
        prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, None)


def test_the_job_records_which_principal_it_runs_as() -> None:
    """An audit trail that says "Frame ran a query" is the thing this design is
    trying not to be true."""
    job = prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, MAYA)
    assert job.credential.subject == "u1"
    assert job.credential.is_service is False


def test_a_service_credential_is_distinguishable_from_a_person() -> None:
    """Non-interactive contexts have no user. The claim is "Frame does not
    implement the policy", never "Frame never holds entitled data" — so a read
    by a service identity must not look like a read by a person."""
    service = Credential(access_token="t", subject="sa-frame-indexer", is_service=True)
    job = prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, service)
    assert job.credential.is_service is True


# --- cost controls, on every job -----------------------------------------


def test_every_job_carries_a_bytes_ceiling() -> None:
    """Enforced by BigQuery, which refuses the job — not checked by Frame after
    the bill arrives."""
    payload = prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, MAYA).to_payload()
    assert payload["configuration"]["query"]["maximumBytesBilled"] == "2000000000"


def test_the_ceiling_is_sent_as_a_string() -> None:
    """The API wants int64 as a string. A number silently drops the ceiling on
    large values — the exact case a ceiling exists for."""
    payload = prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, MAYA).to_payload()
    assert isinstance(payload["configuration"]["query"]["maximumBytesBilled"], str)


def test_a_non_positive_ceiling_is_refused() -> None:
    config = JobConfig(project="frame-local", max_bytes_billed=0)
    with pytest.raises(QueryRefused, match="unbounded"):
        prepare(KEYS_QUERY, {"keys": ["A1"]}, config, MAYA)


def test_every_job_carries_a_timeout() -> None:
    """A query that outlives the request that asked for it is pure cost: nobody
    is waiting for the answer and Frame still pays."""
    payload = prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, MAYA).to_payload()
    assert int(payload["configuration"]["jobTimeoutMs"]) > 0


def test_every_job_is_attributed_to_a_workspace() -> None:
    """Without it the corporate-data spend is one number nobody owns, and the
    first cost review asks a question that cannot be answered
    retrospectively."""
    labels = prepare(KEYS_QUERY, {"keys": ["A1"]}, CONFIG, MAYA).to_payload()["configuration"]["labels"]
    assert labels["app"] == "frame"
    assert labels["workspace"] == "ws-demo"
    assert labels["surface"] == "lookup"


def test_a_label_is_sanitised_to_what_gcp_accepts() -> None:
    """A rejected label fails the whole job, so a workspace named with a capital
    letter would make corporate data stop working for that workspace only."""
    config = JobConfig(project="frame-local", workspace_id="WS Demo/Prod", surface="type ahead")
    labels = config.labels()
    assert labels["workspace"] == "ws-demo-prod"
    assert all(len(v) <= 63 for v in labels.values())


# --- parameter binding ----------------------------------------------------


def test_every_declared_parameter_must_be_supplied() -> None:
    """An unsupplied key list would return no rows, which cannot be told apart
    from a permission denial — the single most misleading outcome available."""
    with pytest.raises(QueryRefused, match="missing query parameter"):
        prepare(KEYS_QUERY, {}, CONFIG, MAYA)


def test_an_array_parameter_is_bound_with_its_declared_element_type() -> None:
    """The gap the dry runs found: IN UNNEST(@keys) against an INT64 column with
    a STRING array is rejected at runtime, and only the catalogue knows the
    column's type."""
    query = fact_measures_at_grain(
        "frame-local", "Facts_Api", "Asset_Transactions", ["Asset", "Period"], ["Amount"],
        grain_types={"Asset": "STRING", "Period": "INT64"},
    )
    bound = {p["name"]: p for p in bind(query, {"Asset": ["A1"], "Period": [202601]})}

    assert bound["Period"]["parameterType"]["arrayType"]["type"] == "INT64"
    assert bound["Asset"]["parameterType"]["arrayType"]["type"] == "STRING"
    assert bound["Period"]["parameterValue"]["arrayValues"] == [{"value": "202601"}]


def test_a_scalar_parameter_keeps_its_declared_type() -> None:
    query = search_labels("frame-local", "Dimensions_Api", "Asset", "Asset", "Asset_Description")
    bound = bind(query, {"prefix": "vehi"})
    assert bound[0]["parameterType"]["type"] == "STRING"
    assert bound[0]["parameterValue"]["value"] == "vehi"


def test_an_array_parameter_given_a_scalar_is_refused() -> None:
    with pytest.raises(QueryRefused, match="ARRAY"):
        bind(KEYS_QUERY, {"keys": "A1"})


def test_a_boolean_binds_as_bigquery_spells_it() -> None:
    from lib.corporate.sql import Query

    query = Query(sql="SELECT 1 WHERE @flag", parameters={"flag": "BOOL"})
    assert bind(query, {"flag": True})[0]["parameterValue"]["value"] == "true"


def test_no_value_is_ever_interpolated_into_the_sql() -> None:
    job = prepare(KEYS_QUERY, {"keys": ["'; DROP TABLE x --"]}, CONFIG, MAYA)
    assert "DROP" not in job.sql
    assert job.parameters[0]["parameterValue"]["arrayValues"] == [{"value": "'; DROP TABLE x --"}]


# --- reading the result ---------------------------------------------------


def test_rows_are_typed_by_the_response_not_the_catalogue() -> None:
    """The catalogue can be stale; the response cannot."""
    result = rows_from_payload({
        "schema": {"fields": [{"name": "Asset"}, {"name": "Asset_Description"}]},
        "rows": [{"f": [{"v": "A1"}, {"v": "Forklift"}]}],
        "totalRows": "1",
        "totalBytesProcessed": "2400000",
    })

    assert result.rows == [{"Asset": "A1", "Asset_Description": "Forklift"}]
    assert result.bytes_processed == 2_400_000
    assert result.truncated is False


def test_a_truncated_result_says_so() -> None:
    """A picker showing the first fifty of nine hundred matches and saying so is
    usable; one that shows fifty and implies that is all of them is
    misleading."""
    result = rows_from_payload({
        "schema": {"fields": [{"name": "Asset"}]},
        "rows": [{"f": [{"v": "A1"}]}],
        "totalRows": "900",
    })
    assert result.truncated is True


def test_an_empty_response_is_not_an_error() -> None:
    assert rows_from_payload({}).rows == []
