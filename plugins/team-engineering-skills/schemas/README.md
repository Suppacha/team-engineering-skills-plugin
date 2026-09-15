# Offline workflow schemas

These schemas document the two JSON inputs accepted by
`scripts/team_workflows.py`. The CLI uses only the Python standard library and
does not persist or transmit either input.

- `traceability.schema.json` describes explicit artifact identifiers and
  references. References point upstream. UI records may be empty because some
  requirements have no UI. Passing this schema and the linkage CLI does not
  certify business completeness.
- `metadata-preview.schema.json` is a strict preview-only allowlist. Retention is
  undecided, and there is no send or persistence action.

Synthetic examples are in `examples/`. They contain no source project data.
