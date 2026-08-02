"""Talking to BigQuery.

The one module that makes a network call. Everything else in `lib/corporate/`
is pure, which is why the sweep, the classifier, the templates and the executor
are all tested without credentials.

Uses the REST API over an access token rather than the `google-cloud-bigquery`
client, and that is a considered choice rather than an omission. The client
resolves credentials through ADC, and the whole point of this feature is that a
query runs as a *specific* principal — the signed-in user for an entitled read,
a declared service identity for the sweep. Handing the client a token per call
means fighting its credential machinery on every request; posting the job
directly means the identity is the one argument that cannot be defaulted.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from lib.corporate.executor import (
    Credential,
    JobConfig,
    QueryFailed,
    Result,
    rows_from_payload,
)
from lib.corporate.sql import Query, ident, project_id

logger = logging.getLogger(__name__)

BIGQUERY_API = "https://bigquery.googleapis.com/bigquery/v2"


class BigQueryClient:
    """Submits jobs. One method, deliberately."""

    def __init__(self, *, http: Any | None = None) -> None:
        # Injected so the transport is substitutable; the default is stdlib so
        # a scheduled job does not need an async client on a loop it does not
        # have.
        self._http = http

    def run(
        self, query: Query, values: dict[str, Any], config: JobConfig, credential: Credential
    ) -> Result:
        from lib.corporate.executor import prepare

        job = prepare(query, values, config, credential)
        payload = job.to_payload()["configuration"]["query"]

        body = {
            "query": payload["query"],
            "useLegacySql": False,
            "parameterMode": "NAMED",
            "queryParameters": payload["queryParameters"],
            "maximumBytesBilled": payload["maximumBytesBilled"],
            "timeoutMs": config.timeout_ms,
            "labels": job.config.labels(),
        }

        if config.location:
            body["location"] = config.location
            # Short-query-optimized mode, and ONLY with a location. BigQuery
            # cannot infer a region for a job it may not create, and asking for
            # the mode without one fails with "Cannot parse  as CloudRegion" —
            # which names neither the missing field nor the feature that
            # required it. Degrading to a normal job is the right trade: slower
            # by a few hundred milliseconds, rather than broken.
            body["jobCreationMode"] = "JOB_CREATION_OPTIONAL"

        response = self._post(
            f"{BIGQUERY_API}/projects/{config.project}/queries",
            body,
            credential.access_token,
        )

        if "error" in response:
            message = str(response["error"].get("message", ""))
            # Left as it came back. A permission failure here is BigQuery
            # telling the user something true about their own access, and
            # replacing it with "corporate data unavailable" would hide the one
            # message that says what to ask for.
            raise QueryFailed(message)

        result = rows_from_payload(response)
        logger.info(
            "corporate query: surface=%s workspace=%s subject=%s rows=%d bytes=%d cached=%s",
            config.surface, config.workspace_id, credential.subject,
            len(result.rows), result.bytes_processed, result.cache_hit,
        )
        return result

    def _post(self, url: str, body: dict[str, Any], token: str) -> dict[str, Any]:
        if self._http is not None:
            return dict(self._http(url, body, token))

        # Checked rather than assumed. The URL is built from a project id that
        # came off a registered Source, and this call carries an access token in
        # a header — a redirect or a scheme confusion here would send a user's
        # BigQuery credential somewhere it does not belong.
        if not url.startswith(BIGQUERY_API + "/"):
            raise QueryFailed(f"refusing to send a credential to {url!r}")

        request = urllib.request.Request(  # noqa: S310 - host checked above
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
                return dict(json.load(response))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                return dict(json.loads(detail))
            except json.JSONDecodeError:
                raise QueryFailed(f"BigQuery returned {exc.code}: {detail[:300]}") from exc


class BigQueryInspector:
    """The probe's `WarehouseInspector`, over the REST API.

    Every method returns `None` rather than raising when it cannot read, because
    the probe's contract is that a failure to gather evidence is recorded and
    forces `entitled`. A raise here would abort the sweep on the first dataset
    Frame lacks a grant on, which is both worse behaviour and the wrong shape:
    "I could not check that one" is per-relation information.

    Results are cached per dataset and per base table. Without it a
    555-dimension sweep asks for the same dataset's IAM 555 times, and the probe
    becomes the expensive part of a job whose whole point is to be cheap enough
    to schedule.
    """

    def __init__(
        self,
        client: BigQueryClient | None = None,
        *,
        config: JobConfig | None = None,
        credential: Credential | None = None,
        http_get: Any | None = None,
    ) -> None:
        self._client = client or BigQueryClient()
        self._config = config
        self._credential = credential
        self._get = http_get
        self._access: dict[str, list[dict[str, Any]] | None] = {}
        self._definitions: dict[str, dict[str, str]] = {}
        self._tags: dict[str, dict[str, tuple[str, ...]] | None] = {}
        self._policies: dict[str, dict[str, int] | None] = {}

    # --- check 1 ----------------------------------------------------------

    def dataset_access(self, project: str, dataset: str) -> list[dict[str, Any]] | None:
        key = f"{project}.{dataset}"
        if key not in self._access:
            self._access[key] = self._fetch_access(project, dataset)
        return self._access[key]

    def _fetch_access(self, project: str, dataset: str) -> list[dict[str, Any]] | None:
        url = f"{BIGQUERY_API}/projects/{project}/datasets/{dataset}"
        try:
            payload = self._http_get(url)
        except Exception:  # noqa: BLE001 - unreadable IAM is evidence, not a crash
            logger.warning("could not read IAM on %s.%s", project, dataset)
            return None
        if "error" in payload:
            return None
        access = payload.get("access")
        return list(access) if isinstance(access, list) else None

    # --- view resolution --------------------------------------------------

    def view_definition(self, project: str, dataset: str, table: str) -> str | None:
        key = f"{project}.{dataset}"
        if key not in self._definitions:
            # One query per dataset, not per view. 555 dimensions across a
            # handful of datasets is a handful of queries.
            self._definitions[key] = self._fetch_definitions(project, dataset)
        return self._definitions[key].get(table)

    def _fetch_definitions(self, project: str, dataset: str) -> dict[str, str]:
        rows = self._query(
            f"SELECT table_name, view_definition "  # noqa: S608 - identifiers validated
            f"FROM `{project_id(project)}.{ident(dataset, 'dataset')}"
            f".INFORMATION_SCHEMA.VIEWS`"
        )
        return {
            str(r.get("table_name")): str(r.get("view_definition") or "")
            for r in (rows or [])
        }

    # --- check 2b ---------------------------------------------------------

    def tagged_columns(self, project: str, dataset: str, table: str) -> tuple[str, ...] | None:
        key = f"{project}.{dataset}"
        if key not in self._tags:
            self._tags[key] = self._fetch_tags(project, dataset)
        tags = self._tags[key]
        return None if tags is None else tags.get(table, ())

    def _fetch_tags(self, project: str, dataset: str) -> dict[str, tuple[str, ...]] | None:
        rows = self._query(
            f"SELECT table_name, field_path "  # noqa: S608 - identifiers validated
            f"FROM `{project_id(project)}.{ident(dataset, 'dataset')}"
            f".INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` "
            "WHERE ARRAY_LENGTH(policy_tags) > 0"
        )
        if rows is None:
            return None
        out: dict[str, list[str]] = {}
        for row in rows:
            out.setdefault(str(row.get("table_name")), []).append(str(row.get("field_path")))
        return {table: tuple(sorted(columns)) for table, columns in out.items()}

    # --- check 2a ---------------------------------------------------------

    def row_access_policy_count(self, project: str, dataset: str, table: str) -> int | None:
        key = f"{project}.{dataset}"
        if key not in self._policies:
            self._policies[key] = self._fetch_policies(project, dataset)
        policies = self._policies[key]
        return None if policies is None else policies.get(table, 0)

    def _fetch_policies(self, project: str, dataset: str) -> dict[str, int] | None:
        """Row access policies, per table.

        Returns `None` against `unops-datahub` today: the
        `INFORMATION_SCHEMA.ROW_ACCESS_POLICIES` view is not readable with the
        access Frame currently has, and reports "not found" rather than an empty
        result. That is recorded as a failed check rather than assumed to mean
        "there are none" — the two are indistinguishable from here, and only one
        of them is safe to act on.
        """
        # One row per policy, counted in Python. Not `COUNT(*) ... GROUP BY`,
        # because the aggregation fence forbids it and the fence is worth more
        # than the convenience. Carving an exception for "but this one is only
        # metadata" is how a rule with no exceptions becomes a rule with one,
        # and the tally is trivial to do here anyway.
        rows = self._query(
            "SELECT table_name "  # noqa: S608 - identifiers validated
            f"FROM `{project_id(project)}.{ident(dataset, 'dataset')}"
            f".INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`"
        )
        if rows is None:
            return None

        counts: dict[str, int] = {}
        for row in rows:
            table = str(row.get("table_name"))
            counts[table] = counts.get(table, 0) + 1
        return counts

    # --- transport --------------------------------------------------------

    def _query(self, sql: str) -> list[dict[str, Any]] | None:
        if self._config is None or self._credential is None:
            return None
        try:
            return self._client.run(Query(sql=sql), {}, self._config, self._credential).rows
        except Exception as exc:  # noqa: BLE001 - an unreadable view is evidence
            logger.info("probe query failed (recorded as an unperformed check): %s", exc)
            return None

    def _http_get(self, url: str) -> dict[str, Any]:
        if self._get is not None:
            return dict(self._get(url))
        if not url.startswith(BIGQUERY_API + "/"):
            raise QueryFailed(f"refusing to send a credential to {url!r}")

        token = self._credential.access_token if self._credential else ""
        request = urllib.request.Request(  # noqa: S310 - host checked above
            url, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            return dict(json.load(response))


class BigQueryMetadataReader:
    """The sweep's `MetadataReader`, over the same client.

    A separate type because the sweep reads *catalogue* queries, which are built
    differently from the four templates — but it runs them through the identical
    cost controls, which is the property worth preserving.
    """

    def __init__(self, client: BigQueryClient | None = None) -> None:
        self._client = client or BigQueryClient()

    def read(self, sql: str, config: JobConfig, credential: Credential) -> list[dict[str, Any]]:
        # Constructed here rather than accepted, so a caller cannot slip a
        # statement past `Query`'s aggregation check by passing a raw string.
        return self._client.run(Query(sql=sql), {}, config, credential).rows
