# Bootdisk ingest 1.0.0rc1

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

The image and source directory are independent inputs. The tool does not mount,
extract, execute, or copy historical software, and does not prove that the directory
came from the image. Preserve original files/images separately: a manifest is not
an archive of their bytes. Exact K.DTX bytes are additionally embedded as base64.

## K-CD without K.DTX

When K.DTX is absent, the same command reads `K-CN.dxr` and `Constant.cxt`
through the experimental Director adapter. It produces a separately versioned
manifest with score-backed program/game candidates, both launch branches,
source references, and explicit conflicts or unresolved mappings. K.DTX-based
input retains its existing behavior. See the [adapter profile, limitations and
Linux ISO test](docs/kcd-director-adapter.md).

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
Python API callers must supply a meaningful timestamp if overriding it and keep
output publication separate from original inputs.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests exercise real temporary files, parser execution, the complete pipeline,
CLI policy, atomic publication, hashing, ISO9660 descriptor bytes and historical
entry reconstruction. The unchanged root `manifest.json` is an immutable reference
fixture; fixture tests are not evidence of a new full-disc ingest.

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
- [ADR-0004: Preservation, provenance and catalog](docs/adr/ADR-0004-domain-separation.md)
- [ADR-0005: Source adapters](docs/adr/ADR-0005-source-adapters.md)
- [ADR-0006: Evidence and publication](docs/adr/ADR-0006-evidence-and-publication.md)
- [Candidate review and remaining limits](docs/release-candidate.md)
- [Historical README](docs/v0.9-readme.md)

No software license has been selected in the baseline repository. This candidate
does not invent a license or alter third-party media rights.

## Experimental Director observations

A read-only Director 6 format reader is available for research and adapter
construction. It preserves structural references, raw bytes and conflicting
script arguments. It does not yet ingest K-CD sources without K.DTX.
See [the reader guide](docs/director-reader.md) for the API, observation command,
qualified formats, optional original-media tests and current limitations.
