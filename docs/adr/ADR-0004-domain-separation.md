# ADR-0004: Separate Preservation, Provenance and Catalog Domains

**Status:** Accepted  
**Date:** 2026-09-05

## Context

Bootdisk started with preservation and ingestion of software distributed on computer magazine media, initially using *Komputer for alle* K-CDs as the first supported source format.

The ingest pipeline can now identify and verify physical media images, logical disc contents, individual files, editorial entries, referenced resources and selected filesystem metadata.

However, K-CD is only one source format.

Bootdisk is intended to support other magazine collections such as HjemmePC, other optical media, floppy disks, archives and standalone software obtained independently of a magazine or physical collection.

The architecture must therefore not assume that software:

- originates from a magazine;
- belongs to an issue;
- exists on optical media;
- has editorial metadata;
- has already been identified;
- or can immediately be associated with a known software product.

Similarly, preservation data must remain valid even when later catalog interpretations change.

A distinction is therefore required between:

1. what Bootdisk possesses or has observed;
2. where an observed object came from;
3. what we believe the object represents.

## Decision

Bootdisk will separate its domain into three loosely coupled concerns:

- **Preservation** — *What do we have?*
- **Provenance** — *Where did it come from?*
- **Catalog** — *What is it?*

The high-level model is:

```text
                    BOOTDISK
                       │
        ┌──────────────┴──────────────┐
        │                             │
  PRESERVATION                    CATALOG
        │                             │
  What do we have?               What is it?
        │                             │
        ▼                             ▼
      Media                       Software
        │                             │
   ┌────┼─────┐                 SoftwareRelease
   │    │     │                       │
 CD-ROM ISO  ZIP                  Artifact
 DVD    IMG  Floppy                   │
   │                                  │
   ▼                                  │
Source / Collection ── Occurrence ────┘
```

Provenance connects preserved objects with the circumstances in which they were found without making the source or collection part of the identity of the object itself.

## Preservation

The Preservation domain records observable and reproducible facts about acquired material.

Examples include:

- media images;
- files and directories;
- file sizes;
- cryptographic hashes;
- logical content identities;
- filesystem metadata;
- filenames and paths;
- source metadata contained on the media.

Preservation data describes what was observed.

It must not require successful identification of the software contained within it.

For example, an executable with an unknown purpose is still a valid preserved Artifact if its bytes and identity can be recorded.

Preservation should favor lossless observation over interpretation.

> **Ingest observes more than it interprets.**

Original values, including unusual spelling, casing, filenames and editorial metadata, should therefore be retained wherever practical.

## Provenance

The Provenance domain records where preserved material came from and the context in which it occurred.

Possible sources include:

- magazine cover discs;
- magazine issues;
- commercial software collections;
- floppy disks;
- CD-ROMs and DVDs;
- downloaded archives;
- standalone files;
- user submissions;
- private collections;
- sources whose origin is unknown.

A source describes origin, not identity.

An **Occurrence** represents the observation that an Artifact appeared in a particular source or context.

The same Artifact may therefore have many Occurrences.

For example:

```text
Artifact
SHA256:b609...
    │
    ├── Occurrence → Komputer for alle 15/2001
    ├── Occurrence → HjemmePC CD
    └── Occurrence → standalone software collection
```

These occurrences do not create three Artifacts.

They provide three pieces of provenance for the same Artifact.

Source-specific structures such as Publication, Issue, Disc or editorial Entry may exist within provenance models or source adapters, but they are not prerequisites for an Artifact to exist.

## Catalog

The Catalog domain describes what preserved artifacts are believed to represent.

The initial conceptual hierarchy is:

```text
Software
    │
    └── SoftwareRelease
            │
            └── Artifact
```

For example:

```text
Winamp
    │
    └── 2.76
          │
          ├── artifact A
          └── artifact B
```

**Software** represents the conceptual product.

**SoftwareRelease** represents a particular version or release of that product.

**Artifact** represents a concrete digital object that can be independently identified, normally through cryptographic content identity.

A SoftwareRelease may have multiple Artifacts.

An Artifact may initially have no associated SoftwareRelease at all.

Catalog information is therefore not required for preservation.

## Artifact identity

Artifact identity must not depend on:

- filename;
- directory;
- magazine;
- issue;
- media;
- editorial title;
- source collection.

Where appropriate, cryptographic content identity should provide the canonical identity of an Artifact.

For example:

```text
artifact_id = sha256:<digest>
```

Byte-identical files discovered in different sources can therefore resolve to the same Artifact while retaining separate Occurrences.

Different artifacts must not be considered identical merely because their filenames, titles or apparent software versions match.

## Source adapters

Source-specific interpretation belongs at the edge of the ingest architecture rather than in the core domain model.

Conceptually:

```text
K.DTX ───────► K-CD adapter ────────┐
                                    │
HjemmePC ─────► HjemmePC adapter ───┤
                                    ├──► Bootdisk preservation model
Directory ─────► Generic adapter ────┤
                                    │
Single file ───► Artifact adapter ───┘
```

A K-CD parser may understand `K.DTX`.

A HjemmePC parser may understand an entirely different metadata format.

The Bootdisk core should not require knowledge of either.

This allows additional source formats to be introduced without redesigning the preservation or catalog domains.

## Independence of entities

The model deliberately permits incomplete relationships.

In particular:

- an Artifact may exist without an Entry;
- an Artifact may exist without a known Source;
- an Artifact may exist without a SoftwareRelease;
- a SoftwareRelease may exist before Bootdisk possesses an Artifact for it;
- Software may exist without any known preserved release;
- a Source may contain no identifiable Software;
- an Occurrence may later be associated with improved catalog information without modifying the underlying preservation record.

Incomplete knowledge is therefore a supported state, not an error condition.

## Evidence and interpretation

Bootdisk should distinguish between different kinds of knowledge.

Future schemas should be capable of distinguishing at least:

**Observed**  
Information directly present in or on the source material.

**Derived**  
Information deterministically calculated from observed material, such as SHA-256 hashes or content identities.

**Interpreted**  
Information inferred from available evidence, such as identifying an artifact as Winamp 2.76.

**Curated**  
Information explicitly reviewed, corrected or confirmed through catalog work.

This distinction allows Bootdisk to explain not only what it knows, but **why it believes it knows it**.

For example:

```text
Title:       WinAmp 2.76
Observed:    K.DTX Titel

Filename:    winamp276_full.exe
Observed:    filesystem

SHA-256:     b609...
Derived:     bootdisk-ingest

Software:    Winamp
Interpreted: catalog

Release:     2.76
Curated:     confirmed catalog record
```

## Consequences

### Positive

Bootdisk is not tied to K-CD or magazine cover discs.

Standalone software can be preserved and cataloged without inventing magazine or publication metadata.

New source formats can be implemented as adapters without changing the core domain model.

Preservation remains stable when catalog interpretations change.

The same Artifact can be recognized across many different collections.

Source history is retained without becoming part of Artifact identity.

Catalog quality can improve independently of the ingest pipeline.

The model supports incomplete and unknown information naturally.

### Negative

The domain model becomes more abstract than a simple Publication → Issue → Disc → Entry hierarchy.

Additional entities and relationships are required.

Catalog resolution becomes a separate problem rather than something ingest can solve implicitly.

Provenance must be modeled explicitly.

Some information may temporarily exist without relationships that users would normally expect, such as an Artifact with no known Software identity.

These costs are accepted because they prevent source-specific assumptions from becoming permanent architectural constraints.

## Constraints

Future Bootdisk development should preserve the following principles:

1. **Preservation must not depend on successful catalog identification.**
2. **Catalog interpretation must not alter original preservation observations.**
3. **Source provenance must not define Artifact identity.**
4. **Source-specific metadata formats belong in adapters rather than the core model.**
5. **Standalone software must be a first-class use case.**
6. **Unknown or incomplete information must be representable without inventing values.**
7. **Derived and interpreted information should be distinguishable from observed source data.**
8. **Original media must never be modified by ingest.**

## Implications for v0.9

v0.9 will establish the core domain boundaries required by this ADR.

The initial model will explore the roles and relationships of:

```text
Source
Collection
Media
Entry
Occurrence
Artifact
SoftwareRelease
Software
```

The purpose of v0.9 is not to finalize every future schema or implement automatic software identification.

Its purpose is to ensure that subsequent development can support multiple source types, independent software artifacts and evolving catalog information without coupling those concerns to the existing K-CD implementation.

## Summary

Bootdisk separates three questions:

> **Preservation — What do we have?**  
> **Provenance — Where did it come from?**  
> **Catalog — What is it?**

These questions are related, but they are not the same question.

Bootdisk will preserve that distinction in its architecture.
