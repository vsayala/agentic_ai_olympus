# Evidence Handling

Operational evidence remains in approved systems with access control, retention, and audit logging.
The external evidence index stores only identifiers, locations, owners, classifications, retention,
and optional hashes. Add a SHA-256 digest when the referenced artifact is immutable and exportable.

Do not place raw prompts, responses, documents, access logs, contracts, personal data, or secrets in
this directory.