# Architecture Decision Records

This directory contains ADRs relevant to `bootdisk-ingest`.

ADR ownership follows architectural scope as defined by the project-level ADR policy in
[`bootdisk/docs/adr/0006-adr-ownership-across-repositories.md`](https://github.com/bootdiskhq/bootdisk/blob/main/docs/adr/0006-adr-ownership-across-repositories.md).

## Ownership

Project-wide and cross-repository decisions are authoritative in the `bootdisk` repository.
Component-local ingest decisions are authoritative in this repository.

ADR numbering is repository-local. Matching numbers in different repositories do not imply
that the files are the same decision.

## Historical mirrors

The following files remain here because they were accepted and used during the ingest
architecture work before ADR ownership was formalized. They are preserved as historical
mirrors and should not be edited as independent sources of truth:

- `ADR-0004-domain-separation.md` — historical mirror of the project-level decision
  [0004-separate-preservation.md](https://github.com/bootdiskhq/bootdisk/blob/main/docs/adr/0004-separate-preservation.md).
- `ADR-0005-source-adapters.md` — historical mirror of the project-level decision
  [0005-Source-adapters-isolate-source-specific-parsing-from-the-preservation-core.md](https://github.com/bootdiskhq/bootdisk/blob/main/docs/adr/0005-Source-adapters-isolate-source-specific-parsing-from-the-preservation-core.md).

If either project-level decision is superseded or amended, the authoritative record in
`bootdisk` governs. The historical mirrors remain unchanged except for an explicit archival
or ownership annotation if needed.

## Ingest-owned ADRs

These decisions are authoritative in `bootdisk-ingest` because they govern the implementation
and contracts of this component:

- [ADR-0006: Preserve metadata evidence and write observations safely](ADR-0006-evidence-and-publication.md)
- [ADR-0007: Director structure is a format layer, not a source adapter](ADR-0007-director-format-observations.md)
- [ADR-0008: Manifest is the contract for publication](ADR-0008-manifest-publication-contract.md)

Cross-repository consumers may link to these ADRs, but should not duplicate their decision
text into another repository.
