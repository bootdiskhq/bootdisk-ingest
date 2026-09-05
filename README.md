# Bootdisk ingest v0.5.1

Patch release for Windows-style case-insensitive path resolution.

## Changes

- Exact path lookup is still attempted first.
- If exact lookup fails, the resolver falls back to `casefold()` matching.
- The original path from K.DTX is preserved.
- The actual path found on disc is stored as `resolved_path` when casing differs.
- Such matches are marked with `path_case_mismatch: true`.
- Folder inventory lookup also falls back to case-insensitive matching.
- Terminal statistics now show the number of case-insensitive path matches.

## Preservation principle

The resolver is tolerant like the original Windows environment, but it does not
rewrite or normalize away historical path casing. Both the source reference and
the actual on-disc spelling are preserved.

## Expected regression baseline

On the current K-CD test disc we expect to return to:

- 39 entries
- 0 missing referenced files
- description_rtf 38/39
- screenshot 39/39
- icon 38/39
- CPU=42: 22 entries
- entry file references: 680
- entry bytes: 556660097
- K.DTX SHA-256:
  `a0fa0a2b5b56ce4f4bc4c8114e9b227a951082a4b8d54442a6356d28b9596eef`

Disc-wide inventory values should remain:

- physical files: 887
- total bytes: 630435653
- unique SHA-256: 823
- duplicate occurrences: 64
