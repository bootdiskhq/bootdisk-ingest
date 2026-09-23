"""Copy explicit observed file references; never infer packages or execute files."""

import json
import hashlib
from pathlib import Path, PurePosixPath
import shutil


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Invalid extraction reference")
    path = PurePosixPath(value)
    if path.is_absolute() or any(x in ("", ".", "..") for x in value.split("/")):
        raise ValueError("Extraction reference must be relative without traversal")
    return path


def _explicit_file_references(entry):
    """Return manifest paths paired with the observed source paths to read.

    ``inventory_refs`` already use observed inventory paths. ``files.discovered``
    deliberately preserves the source metadata spelling in ``path`` and records
    a different ``resolved_path`` when case-insensitive lookup was required.

    Extraction keeps the manifest path as its public identity while reading the
    bytes from the resolved observed path. That makes the manifest-to-extraction
    contract stable without silently rewriting source evidence.
    """

    files = entry.get("files", {})
    refs = {
        path: path
        for path in files.get("inventory_refs", [])
        if isinstance(path, str) and path
    }

    discovered = files.get("discovered", {})
    if isinstance(discovered, dict):
        for observation in discovered.values():
            if not isinstance(observation, dict):
                continue
            if observation.get("exists") is not True:
                continue
            if observation.get("is_file") is not True:
                continue
            manifest_path = observation.get("path")
            if not isinstance(manifest_path, str) or not manifest_path:
                continue
            source_path = observation.get("resolved_path", manifest_path)
            refs[manifest_path] = source_path

    return sorted(refs.items())


def extract_entries(root, manifest, destination):
    """Create a new directory with verified copies and per-entry source metadata.

    The destination must not exist. On failure remove only the directory created
    by this call. A final extraction.json marks successful completion.
    """
    root = Path(root).expanduser().resolve()
    destination = Path(destination).expanduser().absolute()
    resolved = destination.resolve()
    if resolved.is_relative_to(root) or root.is_relative_to(resolved):
        raise ValueError("Extraction destination must be separate from the source tree")

    records = {r["path"]: r for r in manifest["file_inventory"]}
    casefold_records = {}
    for record in manifest["file_inventory"]:
        casefold_records.setdefault(record["path"].casefold(), record)

    planned = []
    for index, entry in enumerate(manifest["entries"], 1):
        refs = []
        for manifest_ref, source_ref in _explicit_file_references(entry):
            target_path = safe_relative(manifest_ref)
            observed_path = safe_relative(source_ref)

            record = records.get(source_ref)
            if record is None:
                record = casefold_records.get(source_ref.casefold())
            if record is None:
                raise ValueError(f"Extraction reference absent from inventory: {manifest_ref}")

            # Read from the exact path preserved by the inventory, even when the
            # manifest reference differs only by case.
            source_path = safe_relative(record["path"])
            source = root.joinpath(*source_path.parts)
            if source.resolve() != source or not source.is_file():
                raise ValueError(f"Extraction source missing or symbolic link: {record['path']}")

            # copied_files must use the manifest identity, because downstream
            # publication resolves assets by the manifest-declared path.
            copied_record = {
                "path": manifest_ref,
                "size": record["size"],
                "sha256": record["sha256"],
            }
            refs.append((target_path, source, copied_record))
        planned.append((f"{index:04d}", entry, refs))

    destination.mkdir()  # Exclusive: --force never authorizes overwriting an extraction.
    try:
        summary = {
            "schema_version": "bootdisk-extraction-1",
            "scope": "Explicit manifest file references; not a complete software-package claim",
            "disc": manifest["disc"],
            "source": manifest["source"],
            "entries": [],
        }
        for directory, entry, refs in planned:
            folder = destination / directory
            folder.mkdir()
            copied = []
            created = []
            for target_path, source, record in refs:
                target = folder / "files" / target_path
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, size = hashlib.sha256(), 0
                # A discovered spelling and an inventory spelling may alias on
                # case-insensitive filesystems. Reuse only our own verified copy
                # of this exact source; retain both manifest paths in metadata.
                alias = target.exists() and any(
                    previous_source == source and target.samefile(previous_target)
                    for previous_source, previous_target in created
                )
                if alias:
                    copied.append(record)
                    continue
                with source.open("rb") as src, target.open("xb") as dst:
                    while block := src.read(1024 * 1024):
                        dst.write(block)
                        digest.update(block)
                        size += len(block)
                if size != record["size"] or digest.hexdigest() != record["sha256"]:
                    raise ValueError(f"Source changed since inventory: {record['path']}")
                copied.append(record)
                created.append((source, target))
            (folder / "entry.json").write_text(
                json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            summary["entries"].append(
                {
                    "directory": directory,
                    "source_id": entry["source_id"],
                    "title": entry["normalized"]["title"],
                    "copied_files": copied,
                    "issues": entry.get("issues", []),
                }
            )
        (destination / "extraction.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except BaseException:
        shutil.rmtree(destination)
        raise
    return summary
