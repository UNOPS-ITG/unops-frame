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
from lib.corporate.sql import Query

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
