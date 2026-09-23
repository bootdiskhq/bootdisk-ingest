# Read-only file inspection

The next step after candidate intake is reusable evidence collection, not automatic
identification. This command inspects explicitly referenced files and, optionally,
nearby text already recorded in the same manifest inventory:

```sh
python -m bootdisk_ingest.inspection /path/to/manifest.json \
  --source /path/to/mounted-disc \
  --cache /path/to/local-cache \
  --output /path/to/new-inspection.json --nearby-text
```

Output/cache must be outside the source tree. Output parent must exist; an existing
output is never overwritten. A later run can use a new output path and the same
cache. Source files are opened only for reading. Nothing is launched, installed,
unpacked or fetched from the network. No new runtime dependency is required.
Supported ingest schemas: `0.9` and `kcd-director-experimental-1`.

## Observations and scope

`bootdisk-file-inspection-1` binds entries to the SHA-256 of the exact manifest and
its entry IDs. File records carry original inventory path, hash, size, read outcome
and a `verified` flag. Each observation has a file byte offset, byte length and
exact excerpt bytes (base64), plus a readable value and the inspector version.
The inspector method is `file-metadata-1`.

- PE32/PE32+ VERSIONINFO is read through the PE resource directory, not by searching
  arbitrary strings. Preserve every supported version resource/language and string
  table. Fixed binary file/product versions remain distinct from string values.
  Repeated keys and contradictory language values are not silently collapsed.
- ProductName, FileDescription, FileVersion and ProductVersion describe the **file**.
  A generic InstallShield/Eschalon/PackageForTheWeb launcher can be shared by entirely
  different programs. These fields never become catalog identity or program version
  automatically. Internal NULs in version strings retain the bytes and a warning.
- `.txt`, `.ini` and `.nfo` supply a readable excerpt and encoding metadata. BOMs are
  respected; UTF-8/CP1252 fallback is explicitly an assumption. Replacement characters
  and excerpt truncation are recorded. INI values are text evidence, not configuration
  instructions for this tool. Descriptions are not rewritten.
- `--nearby-text` selects at most 20 inventory text files in each entry's directly
  referenced parent directories. Every association is `adjacent_text_hint`, never
  proof that the file belongs to this product. Other references retain
  `explicit_reference`. Omitted nearby-file counts are explicit.

The report does not inspect compressed installer members, complete package contents,
DOS/NE executable metadata, deeper directory trees or all CD sections. A missing
version resource is not a claim that no product version exists elsewhere. The source
root must contain the original relative paths. Ingest extraction's per-entry directory
layout is not an interchangeable source root; no fallback search is performed.

## Bounds, failures and cache

Bounds are 64 MiB per binary, 1 MiB per text file, 8192 excerpt bytes, 512 MiB of
requested source bytes per run, 8 MiB of PE resource data, 32 version resources and
512 version blocks per resource. Unsupported/deep/cyclic/malformed PE structures
produce `invalid_format` for this reader, not a declaration that the program itself
is corrupt. Read failures, missing files, hash mismatch, unsupported formats and
size limits are separate outcomes. All source problems remain in the report rather
than forcing manual approval. Source symlinks and special files are rejected.

Cache keys include source SHA-256, decoding mode and inspector version. Identical
launcher bytes reuse decoding, but each source path is read and hash-verified before
using cached results. Missing media cannot be disguised by a cache hit. Read/access
failures are not cached; verified decoding failures may be reused until the inspector
version changes. Concurrent identical cache creation is accepted; contradictory cache
data is an error. The cache is disposable derived data and can be placed in a new
directory if damaged. It is not the authoritative archive or a trust boundary.

Exit 0 means a complete report was produced, including any per-file failure outcomes.
Exit 2 means input/output/cache failure prevented a complete report. Reports contain
no current timestamps, local absolute source path or cache-hit counters: identical
manifest, source bytes, options and inspector version produce identical reports.

## Qualification: K-CD 1/2000

The controlled run covered 21 candidates and 28 file paths, including 7 adjacent
text files. It returned 18 observed files, 5 without PE version resources, 4 formats
not supported by this reader, and 1 VERSIONINFO structure the reader rejected.
All 28 paths matched their inventory hash and size. The existing five menu-link
conflicts remain unresolved; this step does not repair them.

Useful source leads include demo labels in the Prince of Persia 3D and LEGO Loco
setup INIs, VisionDar 5.0 in both setup INI and README, and Excel Viewer product text.
Several other reported versions belong to generic installer engines. These are
inspection findings, not automatic catalog decisions. No original media or generated
reports are committed to the repository.

## Format references and tests

The reader follows Microsoft's [PE resource directory format](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
and [VS_VERSIONINFO layout](https://learn.microsoft.com/en-us/windows/win32/menurc/vs-versioninfo).
These describe the source bytes, not the archive's semantic identification rules.

`python -m unittest discover -s tests -v` includes synthetic PE32/PE32+ resources,
conflicting language values, byte-offset verification, absent resources, malformed
offsets/lengths/cycles, shared launcher caching, source changes, unavailable media,
permissions, symlinks, encoding provenance, adjacent hints and source write exclusion.
