#!/usr/bin/env python
"""Entry point for the scheduled corporate-data sweep.

Run by Cloud Scheduler in a deployment and by hand locally:

    python -m consumers.sweep_corporate_catalogue --workspace ws-demo

**It reads the store directly and that is allowed**, unlike the event consumers
beside it. The fitness rule those obey — refetch through the API under your own
identity — exists because an event consumer acting on row data would bypass the
permission evaluator. This job touches no rows: it reads a registered Source and
writes a catalogue of table names. There is no per-row decision here to bypass.

It writes a GOVERNANCE audit entry, because a sweep changes what an entire
workspace may bind to and can retire a field thousands of rows reference.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger("frame.corporate.sweep")


def load_previous(db: Any, workspace_id: str) -> Any:
    """The catalogue as it stood, so this sweep can say what moved."""
    from lib.corporate.sweep_job import CATALOGUE_COLLECTION, CURRENT, load_catalogue
    from lib.paths import workspace

    snapshot = (
        workspace(db, workspace_id).collection(CATALOGUE_COLLECTION).document(CURRENT).get()
    )
    if not snapshot.exists:
        # None, not an empty catalogue. An empty one would make the first sweep
        # look like every relation had just appeared — and if the comparison
        # ever ran the other way, like every relation had just vanished.
        return None
    return load_catalogue(db, workspace_id)


def sweep_workspace(db: Any, workspace_id: str, source_id: str, actor: str) -> int:
    from api.core.config import get_settings
    from lib.corporate.bigquery import BigQueryMetadataReader
    from lib.corporate.model import Source
    from lib.corporate.sweep_job import audit_entry, persist, run_sweep
    from lib.paths import audit_entry as audit_path
    from lib.paths import workspace

    settings = get_settings()
    billing = settings.corporate_billing_project or settings.gcp_project_id

    document = (
        workspace(db, workspace_id).collection("corporateSources").document(source_id).get()
    )
    if not document.exists:
        logger.error("no corporate source %r registered in workspace %r", source_id, workspace_id)
        return 1

    data = document.to_dict() or {}
    source = Source.model_validate({k: v for k, v in data.items() if k in Source.model_fields})
    if not source.enabled:
        logger.info("source %r is disabled; nothing to sweep", source_id)
        return 0

    credential = _service_credential()
    reader = BigQueryMetadataReader()

    from lib.corporate.bigquery import BigQueryInspector
    from lib.corporate.executor import JobConfig
    from lib.corporate.probe import probe_catalogue

    config = JobConfig(
        project=billing,
        location=source.location,
        max_bytes_billed=source.max_bytes_billed,
        surface="disclosure-probe",
    )

    # The catalogue has to exist before it can be probed — the probe needs to
    # know which relations there are and which datasets they live in. So the
    # sweep runs twice: once to derive, once to classify what it derived.
    # Cheaper than it looks, because the metadata queries hit BigQuery's result
    # cache and the inspector caches per dataset.
    catalogue, result = run_sweep(
        source, reader, credential, billing_project=billing, previous=None
    )
    if result.ok:
        inspector = BigQueryInspector(config=config, credential=credential)
        relations: list[Any] = [*catalogue.dimensions.values(), *catalogue.facts.values()]
        logger.info("probing %d relations for disclosure", len(relations))
        probes = probe_catalogue(relations, inspector, project=source.project)

        catalogue, result = run_sweep(
            source,
            reader,
            credential,
            billing_project=billing,
            previous=load_previous(db, workspace_id),
            probes=probes,
        )

    if not result.ok:
        # Loud, and non-zero, so a scheduler surfaces it. The previous catalogue
        # is left in place — a failed sweep must not look like a mass retirement.
        for error in result.errors:
            logger.error("sweep failed: %s", error)
        return 1

    persist(db, workspace_id, source, catalogue, result)

    import uuid

    audit_path(db, workspace_id, uuid.uuid4().hex).set(
        audit_entry(result, actor=actor, workspace_id=workspace_id).to_document()
    )

    logger.info(
        "swept %s: %d dimensions (%d open), %d facts, %d edges; quarantined %d, restored %d",
        source_id, result.dimensions, result.open_dimensions, result.facts,
        result.relations, len(result.quarantined), len(result.restored),
    )
    for relation_id in result.quarantined:
        logger.warning("QUARANTINED %s — rows referencing it keep rendering, marked stale", relation_id)

    return 0


def _service_credential() -> Any:
    """The sweep's own identity.

    A declared service principal whose BigQuery grants are visible, audited and
    reviewed under PM-9 and PM-11 — not a user's. The catalogue is shared by
    every workspace, so deriving it from one person's entitlements would make
    its contents depend on who happened to trigger it.
    """
    from google.auth import default
    from google.auth.transport.requests import Request

    from lib.corporate.executor import Credential
    from lib.corporate.tokens import BIGQUERY_SCOPE

    credentials, _ = default(scopes=[BIGQUERY_SCOPE])
    credentials.refresh(Request())
    return Credential(
        access_token=credentials.token,
        subject=getattr(credentials, "service_account_email", "application-default"),
        is_service=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep the corporate-data catalogue")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--source", default="datahub")
    parser.add_argument("--actor", default="system:corporate-sweep")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from dotenv import load_dotenv

    load_dotenv("config/.env")

    from lib.firestore import get_db

    return sweep_workspace(get_db(), args.workspace, args.source, args.actor)


if __name__ == "__main__":
    sys.exit(main())
