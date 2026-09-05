# Bootdisk ingest v0.7.0

v0.7.0 adds a deterministic logical identity for the complete disc contents.

## New in v0.7.0

- `disc.content_identity`
- Deterministic SHA-256 across the global physical file inventory
- Identity is based on:
  - actual relative on-disc path
  - SHA-256 of each file
  - deterministic path ordering
- No local mount paths, timestamps, inode metadata or ISO image hash are included

The image SHA-256 from v0.6.0 still identifies the exact disc-image file.
The new disc content identity identifies the logical file contents of the disc.

This means two different ISO images can later be recognized as logically
equivalent if they contain the same paths and identical file bytes, even when
the ISO container bytes themselves differ.

## Run

Mounted disc only:

```bash
python bootdisk_ingest.py /run/media/user/K-CD
```

Mounted disc + original ISO:

```bash
python bootdisk_ingest.py /run/media/user/K-CD \
    --image /archive/K-CD-15-2001.iso
```

## Manifest shape

```json
"disc": {
  "raw": {
    "...": "..."
  },
  "content_identity": {
    "algorithm": "sha256",
    "file_count": 887,
    "total_size": 630435653,
    "manifest_sha256": "..."
  }
}
```

## Identity layers

### Media identity
Identifies the exact image bytes:

```json
"media": {
  "format": "iso",
  "size": 632492032,
  "sha256": "...",
  "media_id": "sha256:..."
}
```

### Disc content identity
Identifies the logical disc file contents:

```json
"disc": {
  "content_identity": {
    "algorithm": "sha256",
    "file_count": 887,
    "total_size": 630435653,
    "manifest_sha256": "..."
  }
}
```

## Regression baseline

The current K-CD test disc should still produce:

- 39 entries
- 0 missing referenced files
- description_rtf 38/39
- screenshot 39/39
- icon 38/39
- 25 case-insensitive path matches
- CPU=42: 22 entries
- 887 physical files
- 630435653 bytes
- 823 unique SHA-256 hashes
- 64 duplicate occurrences
- 680 entry file references
- 556660097 bytes across entries
- K.DTX SHA-256:
  `a0fa0a2b5b56ce4f4bc4c8114e9b227a951082a4b8d54442a6356d28b9596eef`

The new `disc.content_identity.file_count` should be `887` and
`disc.content_identity.total_size` should be `630435653`.

The exact disc content `manifest_sha256` will be determined by the first
successful v0.7.0 run and should then become part of the regression baseline.
