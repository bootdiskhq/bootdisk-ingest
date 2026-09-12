# ADR-0007: Director structure is a format layer, not a source adapter

- **Status:** Accepted
- **Date:** 2026-09-12

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

This change adds an experimental observation command, not a new ingest manifest
schema or an automatic K.DTX fallback. The preservation core and existing adapter
behavior remain unchanged, in line with ADR-0004 through ADR-0006.

## Consequences

A future adapter can join editorial and launch evidence without duplicating binary
parsing. Byte-level tests can run without redistributing historical software;
optional original-byte regressions qualify known samples. Supporting another disc
may require expanding the explicitly qualified profile. Dynamic Lingo behavior,
page reachability and inventory matching remain separate work. A stored EXE
argument is not, by itself, a software occurrence.
