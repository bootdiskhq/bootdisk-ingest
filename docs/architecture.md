# Architecture

Bootdisk separates preservation (observations and identities), provenance
(occurrences and origin), and catalog (software/release interpretation).
Unknown relationships are valid. A byte-identical Artifact has the same identity
across different Sources, filenames and editorial Entries.

## Current responsibilities

| Module | Responsibility |
| --- | --- |
| `core/hashing.py` | Streaming SHA-256 of bytes |
| `core/inventory.py` | Source-relative regular-file observations and lookup |
| `core/identity.py` | Artifact identifiers and stable collection digest |
| `core/models.py`, `core/provenance.py` | Independent entities and occurrence links |
| `adapters/kcd/` | K.DTX, CP1252, editorial fields, path conventions and projections |
| `media.py`, `iso9660.py` | Image identity and bounded filesystem observations |
| `pipeline.py` | Explicit K-CD application workflow |
| `stats.py`, `validation.py`, `output.py` | Existing K-CD manifest summaries and presentation |
| `cli.py` | Input/output policy, timestamps and exit codes |

Core imports only the standard library and other core modules. Source-specific
statistics and validation remain outside core; their historical top-level module
location is not a claim that they are generic domain services. A registry or plugin
framework would add complexity before a second source format establishes its needs.

The workflow inventories source bytes, parses K.DTX using that inventory, attaches
independent image observations, derives statistics and reference validation, then
publishes JSON. Library ingestion does not write files. The CLI checks output
placement before ingest and never executes discovered installers or scripts.

## Evidence versus projection

The INI parser retains historical last-value-wins behavior and case-sensitive keys.
It can normalize whitespace and inherit DEFAULT values. `raw` dictionaries and
`source.sections` are therefore parsed views, not byte-exact transcriptions.
`source.dtx_file.raw_base64` is the lossless evidence for comments, duplicate keys,
line endings, unknown sections and undefined encoding bytes. The corresponding
SHA-256 is checked against inventory before parsing.

CPU=42 and category recognition remain explicitly K-CD interpretations. They do
not identify Software or SoftwareRelease objects. A later catalog decision must
not rewrite the original bytes or file identities.

## Compatibility boundaries

`inventory.py` adapts legacy dictionaries to core FileRecord objects. Its
`build_inventory` name is source-neutral; `build_disc_inventory` remains a callable
compatibility entry point. Rebuilding indexes at this boundary is intentionally
not optimized in this candidate. Introduce a richer adapter interface only with
measured need and tests for its contract.

The original parser module, hashing export, config fields and path helper exports
remain for external callers. The unused content-identity wrapper was already
removed in the baseline commit. Generator and schema versions have separate roles.

## Historical ADR recovery

The baseline commit did not contain a `docs` directory. ADR-0004 and ADR-0005 were
recovered from the referenced conversation, preserving their decision text.
ADR-0004 was initially drafted as ADR-0003; the subsequent conversation explicitly
corrected its number to 0004. No earlier ADRs are invented or renumbered here.
ADR-0006 documents the new candidate decisions, separately from that history.
