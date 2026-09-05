# Bootdisk ingest v0.6.0

v0.6.0 adds stable media identity for the original disc image.

## New in v0.6.0

- Optional `--image` argument
- SHA-256 of the original disc image
- Media size
- Simple image format detection from file extension
- Stable `media_id` using `sha256:<digest>`
- No local image path is stored in the manifest

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

The local filesystem path of the ISO is used only while reading the file.
It is never persisted to `manifest.json`.

## Media manifest example

```json
"media": {
  "available": true,
  "format": "iso",
  "size": 650000000,
  "sha256": "...",
  "media_id": "sha256:..."
}
```

If `--image` is omitted:

```json
"media": {
  "available": false
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
