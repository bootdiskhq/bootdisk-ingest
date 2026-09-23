# Bootdisk ingest 1.0.0rc1

After ingestion, [read-only file inspection](docs/file-inspection.md) can collect
PE version metadata and readable text excerpts as evidence for candidate curation.
It never executes installers or automatically approves software identity/version.

Bootdisk observes historical software sources and records byte identities,
original metadata and provenance. **Parser observes more than it interprets.**
K-CD is the first source adapter; it is not the Bootdisk data model.

This is a **release candidate**, not a claim of completed reference-media
qualification. See [validation and limitations](docs/release-candidate.md).

## Run

Python 3.10 or newer; no runtime dependencies. From a checkout:

```sh
python -m bootdisk_ingest /path/to/K-CD --output /path/to/results/kcd.json
python -m bootdisk_ingest /path/to/K-CD --image /archive/K-CD-15-2001.iso --output /path/to/results/kcd.json
```

Or install with `python -m pip install .` and use `bootdisk-ingest`.
The historical `python bootdisk_ingest.py ...` launcher remains supported.
The output directory must already exist and must be outside the source tree.
The default output is `./ingest-manifest.json`, relative to the current directory.
Existing output requires `--force`; writing never intentionally modifies source
files or the supplied image. Use a stable, preferably read-only source snapshot.

`--quiet` suppresses the historical human-readable report. `--strict` returns 1
if explicit references are missing, after writing the observation manifest.
For the experimental Director adapter it also returns 1 for unresolved or
conflicting primary launch evidence.
Exit 0 means the requested observation completed; exit 2 means input or output
failure. Optional missing editorial assets do not invalidate a source.
For DTX input, `validation.valid` only describes explicit file references, not source authenticity
or completeness. Parser projection warnings are in `source.parser_warnings`.

The image and source directory are independent inputs. The tool does not mount or
execute historical software and does not prove that the directory came from the
image. The manifest records observations; it is not an archive of all source bytes.
Exact K.DTX bytes are additionally embedded as base64.

## K-CD without K.DTX

When K.DTX is absent, the same command reads `K-CN.dxr` and `Constant.cxt`
through the K-CD Director adapter. Director binary parsing itself lives in the
source-agnostic, read-only `bootdisk_ingest/formats/director` format layer; the
K-CD adapter remains responsible for K-CD-specific projection and the ingest
pipeline decides when to use it. The resulting separately versioned manifest
contains score-backed program/game candidates, both launch branches, source
references, and explicit conflicts or unresolved mappings. K.DTX-based input
retains its existing behavior. See the [adapter profile, limitations and Linux ISO
test](docs/kcd-director-adapter.md) and [ADR-0007](docs/adr/ADR-0007-director-format-observations.md).

## Reproducibility

Identities exclude local paths and timestamps. To reproduce the complete JSON:

```sh
SOURCE_DATE_EPOCH=946684800 python -m bootdisk_ingest /path/to/K-CD --output /path/to/results/kcd.json
```

Use the same source bytes, paths, image and generator version. Without that variable,
`generator.generated_at` records the current UTC time. Case-insensitive inventory
ordering has an exact-path tie-break. No source filenames are rewritten.
Symlinks and special files are rejected because the current file-only contract
cannot describe them faithfully. Unreadable files/directories abort observation.

## Python API

```python
from bootdisk_ingest.pipeline import ingest_kcd
manifest = ingest_kcd("/path/to/K-CD", generated_at="2000-01-01T00:00:00+00:00")

from bootdisk_ingest.core.inventory import build_directory_inventory
from bootdisk_ingest.core.identity import build_content_identity
identity = build_content_identity(build_directory_inventory("/path/to/any/files"))
```

The core example requires no magazine metadata. `ingest_kcd` intentionally selects
the K-CD projection. Other source adapters and catalog matching are future work.
Python API callers must supply a meaningful timestamp if overriding it. Library
ingestion returns observations without writing an output file.

## Preservation extraction and publication

`--extract-to /path/to/new-directory` materializes explicit manifest file references
with per-entry metadata and SHA-256 verification. It is a preservation extraction,
not a second source parser and not a complete software-package claim. When source
metadata casing differs from an observed filesystem path, ingest reads the verified
observed path but preserves the manifest-declared path in the extraction contract.
See [scope and usage](docs/extraction.md).

Publication is a separate downstream responsibility. `bootdisk-publish` consumes
the ingest manifest together with preserved extraction bytes; it must not reopen
original media or rediscover K.DTX, Director structures, or other source-specific
metadata. Missing publication-required bytes fail at the preservation contract
instead of causing Publish to fall back to the source. See
[ADR-0008](docs/adr/ADR-0008-manifest-publication-contract.md).

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests exercise real temporary files, parser execution, the complete pipeline,
CLI policy, atomic manifest writing, hashing, ISO9660 descriptor bytes, preservation
extraction and historical entry reconstruction. The unchanged root `manifest.json`
is an immutable reference fixture; fixture tests are not evidence of a new full-disc
ingest.

To qualify against original K-CD 15/2001 media:

```sh
BOOTDISK_KCD_ROOT=/path/to/K-CD BOOTDISK_KCD_IMAGE=/archive/K-CD-15-2001.iso python -m unittest discover -s tests -v
```

Without `BOOTDISK_KCD_ROOT`, one real-media test is explicitly skipped. Supplying
it compares all entries, inventory, statistics, validation and content identity.
Supplying the image additionally verifies image identity and filesystem metadata.

## Architecture and contract

- [Architecture](docs/architecture.md)
- [Manifest compatibility and identities](docs/manifest-contract.md)
- [ADR index and ownership](docs/adr/README.md)
- [Project ADR-0004: Preservation, provenance and catalog](https://github.com/bootdiskhq/bootdisk/blob/main/docs/adr/0004-separate-preservation.md)
- [Project ADR-0005: Source adapters](https://github.com/bootdiskhq/bootdisk/blob/main/docs/adr/0005-Source-adapters-isolate-source-specific-parsing-from-the-preservation-core.md)
- [ADR-0006: Evidence and safe manifest writing](docs/adr/ADR-0006-evidence-and-publication.md)
- [ADR-0007: Director structure as a format layer](docs/adr/ADR-0007-director-format-observations.md)
- [ADR-0008: Manifest is the publication contract](docs/adr/ADR-0008-manifest-publication-contract.md)
- [Candidate review and remaining limits](docs/release-candidate.md)
- [Historical README](docs/v0.9-readme.md)

The local copies of ADR-0004 and ADR-0005 are retained as historical mirrors from
before ADR ownership was formalized. The project-level records linked above are
authoritative.

No software license has been selected in the baseline repository. This candidate
does not invent a license or alter third-party media rights.

## Director format observations

A read-only Director 6 format reader is available for research and adapter
construction. It preserves structural references, raw bytes and conflicting
script arguments. K-CD ingest uses the K-CD Director adapter when K.DTX is absent;
the generic format reader itself does not choose source policy or infer K-CD
semantics. See [the reader guide](docs/director-reader.md) for the API, observation
command, qualified formats, optional original-media tests and current limitations.

## DTX image conventions

Screenshot discovery prefers `Shot.jpg` and falls back to `Shot.bmp` only
when JPG is absent. Case-insensitive resolution retains the observed source
path and hash. If neither exists, the missing asset remains explicit. This
recovers 17 screenshots on K-CD 8/2001 and 32 on K-CD 1/2001; absent images
are not invented.
