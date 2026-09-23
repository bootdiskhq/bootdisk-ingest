# Architecture

Bootdisk separates preservation (observations and identities), provenance
(occurrences and origin), catalog (software/release interpretation), and downstream
publication. Unknown relationships are valid. A byte-identical Artifact has the
same identity across different Sources, filenames and editorial Entries.

The ingest principle is: **parser observes more than it interprets.** Source-specific
knowledge belongs at the source boundary; reusable byte and format observations
should not inherit publication or catalog semantics.

## Current responsibilities

| Module | Responsibility |
| --- | --- |
| `core/hashing.py` | Streaming SHA-256 of bytes |
| `core/inventory.py` | Source-relative regular-file observations and lookup |
| `core/identity.py` | Artifact identifiers and stable collection digest |
| `core/models.py`, `core/provenance.py` | Independent entities and occurrence links |
| `formats/director/` | Checked, read-only Director structure and byte observations |
| `formats/pe_version.py` | Bounded PE VERSIONINFO byte observations, without execution |
| `inspection.py` | Hash-verified file/text observations and versioned decoding cache; no semantic approval |
| `adapters/kcd/` | K.DTX, CP1252, K-CD editorial semantics, Director projection and path conventions |
| `media.py`, `iso9660.py` | Image identity and bounded filesystem observations |
| `pipeline.py` | Explicit K-CD application workflow and parser selection |
| `extraction.py` | Verified materialization of explicit manifest file references |
| `stats.py`, `validation.py`, `output.py` | Existing K-CD manifest summaries and presentation |
| `cli.py` | Input/output policy, timestamps, extraction request and exit codes |

Core imports only the standard library and other core modules. Source-specific
statistics and validation remain outside core; their historical top-level module
location is not a claim that they are generic domain services. A registry or plugin
framework would add complexity before another source adapter establishes its needs.

## Ingest flow

The current application workflow is intentionally K-CD-specific while its lower
layers are reusable:

```text
source directory / optional image
        |
        v
regular-file inventory + media observations
        |
        v
K-CD pipeline selects source projection
   |                         |
K.DTX present            K.DTX absent
   |                         |
K-CD DTX adapter         K-CD Director adapter
                             |
                       formats/director
        |                    |
        +---------+----------+
                  v
        ingest observation manifest
                  |
          +-------+-------+
          |               |
          v               v
 preservation extraction  downstream publication
          |               ^
          +---- verified -+
                bytes
```

When K.DTX exists, the pipeline uses the K-CD DTX parser. When it is absent, the
pipeline dispatches to the K-CD Director adapter. The generic Director format layer
does not make that policy decision and does not assign K-CD meaning to structures.
This boundary is defined by ADR-0007.

Library ingestion returns a manifest without writing files. The CLI checks output
placement before ingest and writes completed JSON atomically. That operation is
manifest writing, not the publication domain. The CLI never executes discovered
installers or scripts.

## Preservation extraction

The manifest is an observation record, not an archive of every source byte.
Preservation extraction materializes only explicit file references described by
the ingest result and verifies their SHA-256 identities while copying.

A source-declared path and an observed filesystem path can differ in casing. In
that case the source-declared path remains the manifest contract, while the
resolved inventory path identifies where verified bytes are read. Extraction writes
the bytes under the manifest-declared path. Downstream consumers therefore do not
need to repeat source-specific case-resolution behavior.

Extraction does not crawl directories to infer software packages, does not execute
payloads, and does not silently promote unrelated files into preservation scope.

## Publication boundary

The ingest manifest is the semantic contract for publication (ADR-0008).
`bootdisk-publish` consumes manifest observations and preservation extraction bytes;
it does not reopen original media or parse K.DTX, Director movies, or future
source-specific formats. If bytes required by an explicit publication observation
are absent or conflict with the manifest identity, publication fails rather than
rediscovering them from the source.

Publication policy is also distinct from preservation evidence. Observing or
preserving a file does not establish redistribution permission. Original bytes,
derivatives and publication metadata remain separate and traceable.

This gives the main boundary:

```text
historical source
      |
      v
bootdisk-ingest  -- source understanding / observations
      |
      +--> ingest manifest -------------------+
      |                                       |
      +--> preservation extraction -- bytes --+--> bootdisk-publish
                                                   |
                                                   v
                                      publication objects / derivatives
```

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
remain for external callers. Generator and schema versions have separate roles.
Manifest schema evolution must consider downstream consumers independently of
repository or release versioning.

## Architectural decisions

ADR-0004 separates preservation, provenance and catalog domains. ADR-0005 keeps
source-specific parsing behind source adapters. ADR-0006 defines evidence retention
and safe manifest writing. ADR-0007 places Director binary structure in a reusable
format layer while leaving source policy to adapters and the pipeline. ADR-0008
makes the ingest manifest the contract for downstream publication.

Together these decisions keep historical-source interpretation in ingest while
allowing preservation, catalog and publication capabilities to evolve without
silently redefining source evidence.
