# Manifest contract and identities

The generator is `1.0.0rc1`; the existing K-CD schema remains `0.9`. Existing keys,
identity framing and projections remain compatible. New evidence fields are
additive and optional for readers of historical manifests:

| Field | Meaning |
| --- | --- |
| `source.dtx_file.raw_base64` | Exact K.DTX bytes encoded as ASCII base64 |
| `source.dtx_file.resolved_path` | Actual metadata filename when casing differs |
| `source.sections` | All parsed sections, including unknown sections |
| `source.defaults` | Parsed INI DEFAULT values |
| `source.parser_warnings` | Loss or ambiguity in the parsed metadata projection |

Consumers must tolerate unknown fields. Strict consumers that reject new keys
need an update before adopting this generator. No existing field is renamed to
make the internal architecture appear more generic. In particular `disc`,
`disc_inventory`, and editorial `entries` remain K-CD manifest vocabulary.
The generator-version change is expected; the reference fixture stays at 0.9.0.

## Three identity levels

1. `media.sha256` hashes exact supplied image bytes. `format` is an extension hint,
   not format verification; a CUE hash identifies only the CUE file, not its tracks.
2. `disc.content_identity.manifest_sha256` hashes logical file observations.
3. Per-file SHA-256 identifies exact file bytes, independent of location.
   Per-entry content identity describes the files associated with an editorial folder.

For logical identity, sort records by exact source-relative POSIX path. Encode
each as UTF-8 `path + NUL + lowercase_sha256 + newline`, concatenate, and SHA-256
the bytes. Report file count and total size separately; size is deliberately not
part of the digest framing. Existing callers must supply observed paths and valid
hashes. The helper is not an untrusted-manifest validator.

Changing source-relative paths changes logical identity. Moving an unchanged
source root does not. Duplicate byte contents retain separate path occurrences.
Inventory presentation sorts by lowercase path and then exact path; identity
always uses the exact-path sort specified above.

## Error and ambiguity behavior

Missing roots, unreadable entries, symlinks and special files abort inventory.
Changes detectable by size, mtime or inode during hashing abort observation.
These checks are not a transactional filesystem snapshot: keep inputs stable.
Empty directories, timestamps, permissions, extended attributes and resource forks
are outside the current file-content inventory contract.

Exact reference matches take precedence. Unique case-insensitive fallbacks retain
the requested path and report the observed resolved path. Ambiguous file or folder
fallbacks raise an error rather than invent a match or merge distinct directories.
The source strings remain unchanged in raw metadata. No path is executed.

ISO9660 recognition is not full filesystem validation. The reader examines at most
128 descriptors, reports missing terminators and both-endian conflicts, and does
not extract files, validate every descriptor field, or parse Rock Ridge/El Torito.
The original image remains the authoritative evidence for unparsed fields.

## K-CD 15/2001 baseline

| Observation | Expected |
| --- | --- |
| Entries | 39 |
| Physical files | 887 |
| Bytes | 630435653 |
| Unique file hashes | 823 |
| Duplicate occurrences | 64 |
| Entry file references | 680 |
| Logical identity | `98227bf06ce1a59b1e3749578e5beedca7558d23df3b4b49f33c323bc9f421ae` |
| Image SHA-256 | `6379da2a559f114941aa206fef0e45710662a519c23b76fe8e145ffa4d78daf3` |
| K.DTX SHA-256 | `a0fa0a2b5b56ce4f4bc4c8114e9b227a951082a4b8d54442a6356d28b9596eef` |

The unchanged reference manifest also records ISO9660 volume `K_CD_15_2001`,
308681 blocks of 2048 bytes, Joliet level 3, and volume name `K-CD 15 2001`.

## Supplementary Tools.dtx and coverage (2026-09-24)

The frozen 39-entry reference above describes K.DTX only, not complete CD content.
Current reads additionally project Tools.dtx I-sections. The existing K source
fields and K entries stay unchanged. New source.supplemental_metadata, source.coverage
and entry.evidence.description_tools fields are documented in [Tools.dtx](tools-dtx.md).
Unknown DTX files/sections are reported; no complete-disc certification is implied.
