# Bootdisk ingest v0.5

v0.5 introduces a disc-wide file inventory.

## What changed

- Every physical file on the mounted disc is hashed once.
- SHA-256 and size are stored in a global `file_inventory`.
- Entries now reference paths in the global inventory through `inventory_refs`.
- Entry `content_identity` is still deterministic and is built from the global file records.
- Statistics distinguish physical files on disc from file references across entries.
- Duplicate file contents on the same disc are detected by SHA-256.

## Run

From the root of a mounted K-CD:

```bash
python /path/to/bootdisk-ingest-v0.5/bootdisk_ingest.py
```

The generated `manifest.json` is written next to the script and is ignored by Git.

## v0.4 baseline

The existing K-CD test disc should still report:

- 39 entries
- 0 missing referenced files
- description_rtf 38/39
- screenshot 39/39
- icon 38/39
- CPU=42 placeholder: 22 entries
- K.DTX SHA-256:
  `a0fa0a2b5b56ce4f4bc4c8114e9b227a951082a4b8d54442a6356d28b9596eef`

The old v0.4 `680` value represented file occurrences across entry folders.
v0.5 additionally reports the actual physical file count for the whole disc.
