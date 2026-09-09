# 1.0.0rc1 review and qualification

Prepared 2026-09-09 from commit
`3757b69cbc350188fe516bd7e55ef1874adafc47`
(`Decouple K-CD content identity from disc-specific logic`).

## Scope and review

The review covered every tracked Python module, both original test modules,
the reference manifest, README, and the available architecture conversation.
The original 15 tests passed before changes. The baseline already removed
`build_disc_content_identity`; its unused hashlib import was removed here.
Tracked interpreter bytecode is removed from the candidate and ignored thereafter.
Compatibility exports with possible external callers remain explicit.

The preservation algorithms remain source-agnostic. K-CD path and editorial
configuration now live in the adapter. No Software/SoftwareRelease matching,
database schema, adapter registry or performance optimization was introduced.
Historical schema field names and logical content-identity framing remain intact.

The important corrected behaviors are loss of metadata evidence, inconsistent
metadata filename resolution, undetected K.DTX changes between hashing and parsing,
silent symlink following, nondeterministic case ties, arbitrary ambiguous fallback,
and output overwriting or contaminating a source inventory.

English documentation explains domain intent, supported evidence, limitations and
compatibility. The original README is retained as a historical document. Recovered
ADR-0004/0005 text and new ADR-0006 distinguish history from candidate decisions.

## Executed verification

| Checkpoint | Result |
| --- | --- |
| Unchanged baseline | 15 passed |
| Preservation safeguards | 19 passed |
| Metadata evidence and adapter boundaries | 24 passed |
| Pipeline and output publication | 32 passed |
| ISO and executed reference regressions | 39 passed, 1 real-media test skipped |
| Final candidate | 43 passed, 1 real-media test skipped (44 total) |

The final tests run on bundled CPython 3.12 on macOS. The configured CI matrix
targets Python 3.10, 3.12 and 3.14 on Linux; those remote jobs have not run here.
Tests cover byte fixtures, real temporary files, CLI entry-function behavior,
atomic-write failure preservation, metadata parsing and pipeline orchestration.
The module CLI also completed a separate synthetic-source invocation successfully.
The wheel built, installed into an isolated target, and reported version 1.0.0rc1.
The source distribution built successfully.

This host kills some nested interpreter processes and restricts in-place workspace
operations. CLI policy tests therefore call the real main function in-process;
the module launcher was checked separately. Packaging used the standard setuptools
backend in-process and pip installed the resulting wheel. These environment
workarounds are not added to the project runtime.

Executed reference checks rebuild all 39 entries and their identities from stored
observations, recompute the global identity from all 887 inventory records, and
compare complete statistics and validation. They reproduce the known regression
values in [the contract](manifest-contract.md). The original reference manifest
is unchanged. These checks do not rehash the original historical files.

## Remaining qualification and limits

No K-CD ISO, K.DTX source tree or mounted K-CD was found in the inspected Documents,
Downloads, Desktop or local volume listings. The real-media test is explicitly
skipped until BOOTDISK_KCD_ROOT is supplied; image qualification additionally needs
BOOTDISK_KCD_IMAGE. Run that check before promoting this candidate to final 1.0.

The CLI supports K-CD sources; the core can inventory unrelated directories.
Additional source adapters, automated catalog identification, payload archival,
and image mounting/extraction are not implemented. A manifest is an observation
record, not a backup of the source payloads.

Inputs must remain stable. File-change checks are best-effort, not a snapshot or
protection against adversarial concurrent filesystem changes. Image/directory
correspondence is unverified. Empty directories, permissions, timestamps, extended
attributes, resource forks, symlinks and special files are outside the current
inventory contract. Unsupported objects fail instead of being silently omitted.

INI projections can normalize data; exact K.DTX bytes remain available. Malformed
INI aborts ingestion rather than producing a misleading successful manifest.
ISO9660 inspection is bounded and partial; recognition does not certify validity.
Atomic publication requires link/replace support on the output filesystem and
does not promise full filesystem crash durability. No software license was chosen
because the baseline contains none.

No remote push, tag or release publication is part of this delivery.
