# ADR-0005: Source adapters isolate source-specific parsing from the preservation core

- **Status:** Accepted
- **Date:** 2026-09-08

## Context

Bootdisk is intended to preserve and describe historical software from many different kinds of sources.

The first supported source format is the K-CD distributed with *Komputer for alle*. The initial ingest implementation was therefore naturally built around concepts found on that particular source, including:

- `K.DTX`
- K-CD-specific metadata fields
- editorial entries
- CD-oriented terminology
- Windows-style paths
- source-specific path inconsistencies

As the ingest system evolved, several operations originally implemented as part of the K-CD pipeline turned out not to be specific to K-CD at all.

Examples include:

- discovering files
- recording relative file paths
- recording file sizes
- calculating SHA-256 hashes
- building deterministic content identities
- exact path lookup
- case-insensitive path fallback
- representing preserved file observations

These operations are equally applicable to other sources such as:

- other magazine CDs and DVDs
- floppy disks
- disk images
- extracted archives
- software collections
- standalone files
- user-submitted material

Keeping these operations inside a K-CD- or disc-specific implementation would incorrectly make the first supported source format part of the architectural foundation of Bootdisk.

Bootdisk must instead be able to ingest new source types without requiring the preservation core to understand their publication-specific formats.

This follows the broader domain separation established in ADR-0004:

> Preservation records what exists.  
> Provenance records where it came from.  
> Catalog describes what it is.

It also follows the ingest principle:

> **Ingest should be lossless. Parser observes more than it interprets.**

## Decision

Bootdisk ingest will separate **source-specific parsing** from the **source-agnostic preservation core**.

Source-specific knowledge will be implemented through **source adapters**.

The architecture will follow this general direction:

```text
bootdisk-ingest
    |
    +-- core
    |   +-- hashing
    |   +-- inventory
    |   +-- identity
    |   +-- provenance
    |   +-- models
    |   +-- validation
    |
    +-- adapters
        +-- kcd
        +-- ...
```

The preservation core must not require knowledge of a particular publication, magazine, disc layout, metadata file, or editorial format.

A source adapter is responsible for understanding the conventions of a particular source format and translating observations from that source into structures understood by the rest of the ingest system.

For example, the K-CD adapter may understand:

- the `K.DTX` metadata file
- its CP1252 encoding
- `[Generelt]`
- `Kxx` sections
- K-CD category fields
- K-CD-specific editorial metadata
- historical path conventions used by the source

The generic core must not understand those concepts.

Conversely, generic operations such as hashing or file inventory must not be reimplemented by individual source adapters.

## Preservation core

The preservation core operates on source-independent observations.

A file observation is represented by `FileRecord`:

```python
@dataclass(slots=True, frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str
```

The path is relative to the observed source root.

Machine-specific information such as local mount paths is deliberately excluded from the preserved identity.

Collections of file observations are represented by `FileInventory`, which provides generic lookup behaviour while retaining the original observations.

The core currently provides functionality including:

- deterministic directory inventory
- SHA-256 hashing
- deterministic logical content identity
- exact path lookup
- case-insensitive path fallback
- folder lookup

These capabilities must remain independent of whether the files originated from a CD-ROM, floppy disk, archive, directory, disk image, or another source.

## Source adapters

Source adapters contain knowledge that only makes sense for a particular source format.

The first adapter is:

```text
bootdisk_ingest/adapters/kcd/
```

Its parser is responsible for interpreting the structure of K-CD metadata while relying on generic core functionality for preservation operations.

Conceptually:

```text
                  Source
                     |
                     v
             +---------------+
             | Source adapter|
             +---------------+
                     |
          source-specific observation
                     |
                     v
        +--------------------------+
        | Source-agnostic core     |
        |                          |
        | inventory                |
        | hashing                  |
        | identity                 |
        | provenance               |
        +--------------------------+
```

Future adapters may support formats such as other magazine cover media, software collections, generic directories, or standalone material.

The existence of a new source type should normally require a new adapter or source reader, **not changes to the fundamental preservation algorithms**.

## Raw source metadata

Source-specific raw metadata may be preserved by an adapter.

For example, values from the K-CD `[Generelt]` section are observations of the original source and should not be discarded merely because they are not generic.

Preserving raw metadata does not make that metadata part of the generic domain model.

This distinction allows Bootdisk to retain historically significant details, including:

- original spelling
- original casing
- editorial inconsistencies
- unusual values
- unknown fields
- source-specific conventions

Normalization or interpretation must not silently overwrite the original observation.

## Content identity

Logical content identity is a generic preservation operation.

It must therefore be calculated by the source-agnostic core rather than by a disc- or adapter-specific implementation.

For example:

```python
from bootdisk_ingest.core.identity import build_content_identity
```

The identity describes the observed file collection and does not inherently describe a "disc".

A CD-ROM may have such an identity, but so may an extracted archive, floppy image, software collection, or directory.

Existing manifest field names may temporarily retain historical terminology for schema compatibility. Internal architecture must not depend on that terminology.

Schema migration and architectural refactoring are intentionally treated as separate concerns.

## Compatibility

Existing manifest structures must not be changed merely as a side effect of moving functionality into the generic core.

For example, the current manifest may still contain structures such as:

```json
{
  "disc": {
    "content_identity": {}
  }
}
```

even though the identity itself is now produced by the generic preservation core.

This allows the implementation to evolve without unnecessarily invalidating existing manifests, regression fixtures, or downstream consumers.

Compatibility wrappers may temporarily remain while callers are migrated.

They should be removed when they are no longer used.

## Consequences

### Positive

- New source formats can be added without duplicating preservation logic.
- The first supported format does not define the architecture of the entire project.
- Preservation behaviour becomes reusable and independently testable.
- Source-specific quirks remain isolated in the adapter that understands them.
- Standalone files and non-publication sources become first-class architectural possibilities.
- Generic concepts receive generic names.
- Refactoring can occur without simultaneously changing the manifest schema.
- Historical source metadata can remain lossless while normalized representations evolve independently.

### Negative

- The codebase contains more explicit architectural boundaries.
- Some temporary compatibility wrappers may exist during migration.
- Data may cross representation boundaries between legacy dictionaries and core models.
- Adding a source may require deciding carefully whether behaviour belongs in the adapter or in the core.

These costs are accepted because explicit boundaries are preferable to allowing source-specific assumptions to spread through the preservation system.

## Boundary rule

When adding new ingest behaviour, use the following rule:

> **If the behaviour would still make sense for an unrelated historical software source, it probably belongs in the core.**

> **If the behaviour exists because of the conventions of a particular source, publication, metadata format, or collection, it belongs in an adapter.**

When uncertain, prefer keeping source-specific interpretation outside the preservation core until there is evidence that the concept is genuinely generic.

## Examples

### Belongs in the core

```text
SHA-256 calculation
FileRecord
FileInventory
Deterministic content identity
Relative file observations
Exact path lookup
Case-insensitive lookup fallback
Generic provenance primitives
```

### Belongs in the K-CD adapter

```text
K.DTX parsing
CP1252 handling for K.DTX
[Generelt]
Kxx sections
K-CD category interpretation
CPU=42 interpretation
K-CD editorial asset conventions
```

## Future direction

This decision establishes the architectural foundation for additional ingest adapters.

Possible future source types include:

```text
adapters/
    kcd/
    hjemmepc/
    generic_directory/
    standalone_file/
```

These names are illustrative rather than commitments to specific implementations.

Media-format handling such as ISO9660 parsing is related but distinct from source adapters. A filesystem or media format describes how bytes and files are stored; a source adapter describes how a particular source organizes and describes its content.

Bootdisk should therefore avoid assuming that:

```text
source == publication == medium == filesystem
```

These concepts may coincide for a particular historical disc, but they represent different architectural concerns.

## Decision summary

Bootdisk will treat source-specific formats as adapters around a source-agnostic preservation core.

K-CD is the first supported source format.

It is **not** the Bootdisk data model.

The preservation core must remain capable of describing software material regardless of whether it came from a magazine CD, DVD, floppy disk, disk image, archive, directory, collection, standalone file, or a source type not yet anticipated.
