# ADR-0008: Manifest is the contract for publication

- **Status:** Accepted
- **Date:** 2026-09-14

## Context

Bootdisk separates source understanding, preservation and publication. Ingest can
observe source-specific structures such as K.DTX metadata, Director resources and
filesystem relationships, while publication needs a stable description of the
observed material without learning how each historical source format works.

Allowing publication tooling to reopen original media or repeat source-specific
parsing would duplicate ingest logic, weaken provenance boundaries and make
publication behavior depend on source availability. It would also make future
source adapters part of the publication implementation even when they expose the
same source-agnostic observations.

The preservation extraction provides verified bytes for explicitly preserved
manifest references. Publication therefore needs two related inputs: the ingest
manifest describing what was observed and the preservation extraction supplying
the bytes that were preserved for those observations.

## Decision

The ingest manifest is the semantic contract between `bootdisk-ingest` and
publication tooling. `bootdisk-publish` consumes observations expressed by that
manifest and remains source-format agnostic. It must not parse K.DTX, Director
movies, publication-specific metadata or future source formats in order to decide
what ingest observed.

Publication must not fall back to the original source medium when required bytes
are absent from the preservation extraction. A manifest observation that is to be
materialized must resolve to preserved bytes whose identity agrees with the
manifest, including size and cryptographic hash. Missing or conflicting evidence
fails explicitly rather than being repaired by rediscovery.

The manifest path is part of the contract and preserves the source-declared
identity of a reference. Ingest may use a separately observed resolved path to read
source bytes, for example after an unambiguous case-insensitive filesystem match,
but preservation extraction materializes those bytes under the manifest-declared
path so downstream consumers do not need source-specific path-resolution rules.

Publication policy is separate from observation. The presence of an artifact,
asset or software payload in an ingest manifest does not by itself grant permission
to redistribute it. Publication may create derivatives and expose material only
according to explicit publication policy. Original preserved bytes, generated
derivatives and publication metadata remain distinguishable and traceable.

`bootdisk-publish` may emit its own publish manifest describing published objects,
derivatives and stable object keys. That output is a publication product; it does
not replace or reinterpret the ingest manifest as evidence of the source.

## Consequences

New source adapters can be added to ingest without adding equivalent parsers to
`bootdisk-publish`, provided they express observations through the supported
manifest contract. Publication can be tested independently of historical source
formats and original media.

The boundary is intentionally strict. If ingest fails to preserve bytes required
for an explicit publication observation, ingest or the preservation contract must
be corrected instead of teaching publication how to recover the bytes from the
source. This makes contract gaps visible and keeps source interpretation in one
place.

Schema evolution must consider downstream consumers explicitly. Changes to the
manifest that alter publication-relevant semantics require compatibility handling
or a deliberate contract version change; repository or release version numbers
alone do not redefine those semantics.

This ADR clarifies the word "publish" used in ADR-0006: ADR-0006 uses it for the
atomic writing of a completed ingest JSON file. That operation is distinct from
the `bootdisk-publish` component and the publication domain defined here.
