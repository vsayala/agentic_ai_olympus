# Release and Rollback

## Versioning

Use Semantic Versioning. Update `project.version` in `pyproject.toml`, move relevant entries from
`Unreleased` in `CHANGELOG.md`, refresh `uv.lock`, and merge through the protected default branch.
The release tag must be exactly `v<project.version>`.

## Release

1. Confirm root and nested Databricks gates pass for the release revision.
2. Obtain fresh Loki, Thor, and Hela receipts and Odin's final status.
3. Confirm no unresolved security alerts and complete authenticated Databricks validation when the
   release includes cloud resources.
4. Push the signed version tag or manually run **Release artifacts** with the matching version.
5. Approve the protected `release` environment. The workflow rebuilds from source, emits a
   CycloneDX SBOM, creates GitHub artifact provenance, and uploads the wheel, sdist, and SBOM.
6. Verify the attestation and install the wheel in a clean environment before distribution.

## Rollback

Application rollback uses the last verified wheel and source revision; never rebuild an old version
from a newer branch. Verify its provenance and SBOM, redeploy through the same protected environment,
and run the launcher/retrieval smoke tests.

Databricks rollback uses the last reviewed bundle revision and target. Validate the bundle, inspect
the resource diff, deploy through the protected target environment, and verify source acquisition,
tables, indexes, serving, failure logs, and idempotent rerun behavior. Do not automatically delete
durable catalogs or production data. Open an incident record describing reason, approver, artifacts,
validation, and any required forward fix.