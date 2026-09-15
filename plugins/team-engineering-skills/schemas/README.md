# Offline workflow schemas

These schemas are structural subsets of the two JSON input contracts enforced
by `scripts/team_workflows.py`. Schema validation alone does not establish that
the CLI will accept an input. The offline CLI is authoritative, uses only the
Python standard library, and does not persist or transmit either input.

- `traceability.schema.json` describes explicit artifact identifiers and
  references. References point upstream. UI records may be empty because some
  requirements have no UI. Passing this schema and the linkage CLI does not
  certify business completeness.
- `metadata-preview.schema.json` is a strict preview-only allowlist. Retention is
  undecided, and there is no send or persistence action.

Synthetic examples are in `examples/`. They contain no source project data.

Constraints intentionally enforced only by the CLI are:

- a 1 MiB limit on each input file;
- canonical lowercase UUID-v4 spelling for metadata `project_id` and the exact
  `task_category` to `selected_skill` pairing;
- layer-specific identifier prefixes (`REQ-`, `UC-`, `UI-`, `TS-`, and `TC-`),
  globally unique traceability identifiers, existing reference targets, and
  references that point only to an upstream layer (cycles are unsupported).

Run the matching CLI command after schema-based authoring or editor checks:
`validate-traceability` or `preview-metadata`.
