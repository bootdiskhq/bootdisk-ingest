# ADR-0007: Director structure is a format layer, not a source adapter

- **Status:** Accepted
- **Date:** 2026-09-12
- **Updated:** 2026-09-14

## Context

Older K-CD frontends store editorial text and interaction scripts in Director
movies and external casts rather than K.DTX. Shared casts contain stale data;
some score-linked install scripts even disagree with their warning-page scripts.
Text matching alone cannot reliably identify program entries or launch targets.

## Decision

Add `bootdisk_ingest/formats/director` as a checked, read-only format layer. It
exposes resource maps, cast relationships, bytes, script contexts/instructions,
literal-call observations and sequential score state. K-CD-specific labels,
titles, reachability and filesystem matching remain outside this package.

Original references and byte values are retained. Missing external casts remain
unresolved; source-provided paths do not authorize automatic filesystem reads.
Unused context entries and contradictory call arguments are not silently discarded.
Unsupported variants fail explicitly instead of being parsed using guessed offsets.

The Director format layer itself does not decide when a source should be interpreted
as K-CD, nor does it implement K-CD-specific fallback policy. That decision belongs
in the K-CD ingest orchestration and adapter boundary.

For K-CD ingest, the current pipeline uses K.DTX when that metadata file is present.
When K.DTX is absent, the pipeline dispatches to the K-CD Director adapter, which
uses the generic Director format layer to derive source-specific observations. This
is an ingest selection policy, not a responsibility of `formats/director`.

This behavior does not make Director a source adapter and does not move K-CD
semantics into the format layer. The preservation core remains source-agnostic, in
line with ADR-0004 through ADR-0006.

## Consequences

A source adapter can join editorial and launch evidence without duplicating binary
parsing. Byte-level tests can run without redistributing historical software;
optional original-byte regressions qualify known samples. Supporting another disc
may require expanding the explicitly qualified profile. Dynamic Lingo behavior and
other source-specific interpretation remain separate concerns. A stored EXE
argument is not, by itself, a software occurrence.

The K-CD pipeline may use Director-derived observations when K.DTX is absent, while
other future source adapters can reuse the Director format layer under different
selection and interpretation policies.
