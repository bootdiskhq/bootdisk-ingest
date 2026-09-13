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
    """Return every file path that the manifest explicitly associates with an entry.

    ``inventory_refs`` remains the preservation package view used by existing
    adapters. ``files.discovered`` may additionally identify exact observed
    assets such as screenshots and icons. Extraction must preserve both sets so
    downstream consumers can materialize manifest-declared assets without ever
    returning to the original source medium.

    This intentionally does not scan directories or infer neighboring files.
    """

    files = entry.get("files", {})
    refs = set(files.get("inventory_refs", []))
    discovered = files.get("discovered", {})
    if isinstance(discovered, dict):
        for observation in discovered.values():
            if not isinstance(observation, dict):
                continue
            if observation.get("exists") is not True:
                continue
            if observation.get("is_file") is not True:
                continue
            path = observation.get("path")
            if isinstance(path, str) and path:
                refs.add(path)
    return sorted(refs)


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
    planned = []
    for index, entry in enumerate(manifest["entries"], 1):
        refs = []
        for ref in _explicit_file_references(entry):
            path = safe_relative(ref)
            if ref not in records:
                raise ValueError(f"Extraction reference absent from inventory: {ref}")
            source = root.joinpath(*path.parts)
            if source.resolve() != source or not source.is_file():
                raise ValueError(f"Extraction source missing or symbolic link: {ref}")
            refs.append((ref, source, records[ref]))
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
            for ref, source, record in refs:
                target = folder / "files" / ref
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, size = hashlib.sha256(), 0
                with source.open("rb") as src, target.open("xb") as dst:
                    while block := src.read(1024 * 1024):
                        dst.write(block)
                        digest.update(block)
                        size += len(block)
                if size != record["size"] or digest.hexdigest() != record["sha256"]:
                    raise ValueError(f"Source changed since inventory: {ref}")
                copied.append(record)
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
