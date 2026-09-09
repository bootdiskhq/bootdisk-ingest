# ADR-0006: Preserve metadata evidence and publish observations separately

- Status: Accepted for 1.0.0rc1
- Date: 2026-09-09

## Context

ConfigParser dictionaries lose comments, duplicate fields and byte-level details.
Replacement decoding can hide encoding damage. The original launcher overwrote
the repository reference manifest and could include output in subsequent source
inventories. File traversal could silently represent symlink targets as ordinary
source bytes. These behaviors conflict with ADR-0004 and ADR-0005.

## Decision

Retain the legacy K-CD projection and content-identity framing. Add exact K.DTX
bytes as base64 with parsed-section views and explicit projection warnings. Verify
the metadata bytes against the inventory before parsing. Source evidence and
interpretation remain separate; do not promote K-CD fields into core models.

Inventory regular files explicitly. Reject unsupported symlinks and special files,
propagate access errors, and detect common concurrent file changes. Require stable
inputs; do not pretend these checks create a transactional snapshot. Resolve
case-insensitive references only when the matching file or folder is unambiguous.

Expose a library pipeline that returns a manifest without writing. The CLI requires
output outside the source tree, protects the supplied image, defaults to a new
output filename, and requires explicit replacement of existing output. Publish
complete JSON through a sibling temporary file and atomic link/replace operations.
The output filesystem must support those operations; failures are reported.

Support SOURCE_DATE_EPOCH for repeatable full-manifest bytes. Keep schema 0.9 with
documented optional evidence fields; release versioning does not mandate a schema
rename. Consumers rejecting unknown fields must update explicitly.

## Consequences

Exact source evidence survives lossy parsed views. Existing K-CD projections stay
comparable, and new adapters do not inherit K-CD semantics. Reproduction is possible
with fixed inputs and generator metadata. Parser and publication errors cannot be
mistaken for a successful empty ingest.

Manifests become larger because metadata bytes are embedded. Unsupported source
objects fail rather than being silently omitted. The tool still does not archive
all payload bytes, prove image/directory correspondence, or solve catalog identity.
Those are separate capabilities, not implicit promises of this candidate.
