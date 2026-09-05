# Bootdisk ingest v0.8.0

v0.8.0 adds direct observation of ISO9660 filesystem metadata from the original disc image.

## New in v0.8.0

- Built-in ISO9660 volume descriptor reader
- No external tools or new dependencies
- Primary Volume Descriptor metadata
- Joliet detection and level reporting
- Both-endian numeric consistency checks
- No local image path is stored in the manifest

The existing identity layers remain unchanged:

- `media.sha256` identifies the exact image bytes
- `disc.content_identity.manifest_sha256` identifies the logical file contents
- `disc.filesystem` now records observable filesystem metadata from the image

## Observed ISO9660 fields

`disc.filesystem.primary_volume_descriptor` records:

- system ID
- volume ID
- volume space size
- volume set size
- volume sequence number
- logical block size
- path table size
- volume set ID
- publisher ID
- data preparer ID
- application ID
- ISO9660 volume timestamps
- file structure version

Numeric ISO9660 fields encoded in both little-endian and big-endian form are retained as:

```json
{
  "value": 2048,
  "little_endian": 2048,
  "big_endian": 2048,
  "consistent": true
}
```

If the two representations disagree, `value` becomes `null`, both original interpretations are preserved, and the field is listed in `numeric_endianness_mismatches`.

## Joliet

Supplementary Volume Descriptors using the standard Joliet escape sequences are detected. The manifest records the descriptor sector, Joliet level, escape sequence and Joliet volume ID.

v0.8.0 intentionally does not interpret Rock Ridge, El Torito or other extensions yet.

## Run

```bash
python bootdisk_ingest.py /run/media/user/K-CD \
    --image /archive/K-CD-15-2001.iso
```

## Regression baseline

All v0.7.0 reference-disc values must remain unchanged, including:

- 39 entries
- 887 physical files
- 630435653 bytes
- 823 unique SHA-256 hashes
- 64 duplicate occurrences
- 680 entry file references
- disc content identity:
  `98227bf06ce1a59b1e3749578e5beedca7558d23df3b4b49f33c323bc9f421ae`
- image SHA-256:
  `6379da2a559f114941aa206fef0e45710662a519c23b76fe8e145ffa4d78daf3`
- K.DTX SHA-256:
  `a0fa0a2b5b56ce4f4bc4c8114e9b227a951082a4b8d54442a6356d28b9596eef`

The first successful v0.8.0 reference run establishes the expected ISO9660/Joliet metadata for K-CD 15/2001.
