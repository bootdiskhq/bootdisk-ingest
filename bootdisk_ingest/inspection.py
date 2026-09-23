"""Read-only, hash-bound file inspection; no identification or approval writes."""
import argparse
import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

from .formats.pe_version import PEError, version_observations
from .output import write_manifest

METHOD = "file-metadata-1"
MAX_FILE = 64 * 1024 * 1024
MAX_TEXT = 1024 * 1024
MAX_NEARBY = 20
MAX_TOTAL = 512 * 1024 * 1024
TEXT_SUFFIXES = {".txt", ".ini", ".nfo"}


def _result(status, **details):
    return dict(status=status, observations=[], **details)


def inspect_bytes(data, mode):
    if mode == "pe":
        try:
            return version_observations(data)
        except (PEError, UnicodeError) as exc:
            return _result("invalid_format", message=str(exc))
    if len(data) > MAX_TEXT:
        return _result("size_limit")
    # Encoding is explicit when a BOM exists; otherwise retain an encoding
    # assumption and exact excerpt bytes so the display can be reinterpreted.
    offset, encoding, assumed = 0, "utf-8", True
    if data.startswith(b"\xff\xfe"):
        offset, encoding, assumed = 2, "utf-16le", False
    elif data.startswith(b"\xfe\xff"):
        offset, encoding, assumed = 2, "utf-16be", False
    elif data.startswith(b"\xef\xbb\xbf"):
        offset, encoding, assumed = 3, "utf-8", False
    else:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            encoding = "cp1252"
    excerpt = data[offset:offset + 8192]
    text = excerpt.decode(encoding, errors="replace")
    if "\0" in text or sum(ord(c) < 32 and c not in "\r\n\t" for c in text) > max(2, len(text) // 50):
        return _result("unsupported_format", message="not a supported plain-text view")
    return dict(status="observed", observations=[dict(field="text_excerpt", value=text,
                offset=offset, length=len(excerpt), encoding=encoding, encoding_assumed=assumed,
                truncated=offset + len(excerpt) < len(data), decoding_replacements="\ufffd" in text,
                raw_base64=base64.b64encode(excerpt).decode("ascii"))])


def _path(root, relative):
    path = PurePosixPath(relative)
    if (not relative or path.is_absolute() or any(p in ("", ".", "..") for p in relative.split("/"))
            or "\\" in relative or "\0" in relative):
        raise ValueError("unsafe source-relative path")
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError("symlink source path is not supported")
    return target


def inspect_file(root, item, cache):
    """Verify bytes before using cached decoding. Read failures are not cached."""
    mode = "text" if PurePosixPath(item["path"]).suffix.lower() in TEXT_SUFFIXES else "pe"
    limit = MAX_TEXT if mode == "text" else MAX_FILE
    try:
        path = _path(root, item["path"])
        if not stat.S_ISREG(path.stat().st_mode):
            return _result("unsupported_file", verified=False)
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                return _result("unsupported_file", verified=False)
            if before.st_size > limit:
                return _result("size_limit", verified=False)
            data = handle.read(limit + 1)
            after = os.fstat(handle.fileno())
    except FileNotFoundError:
        return _result("missing_file", verified=False)
    except PermissionError:
        return _result("permission_denied", verified=False)
    except OSError as exc:
        return _result("read_error", verified=False, errno=exc.errno)
    except ValueError as exc:
        return _result("unsafe_path", verified=False, message=str(exc))
    if len(data) > limit:
        return _result("size_limit", verified=False)
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        return _result("changed_during_read", verified=False)
    digest = hashlib.sha256(data).hexdigest()
    if digest != item["sha256"] or len(data) != item["size"]:
        return _result("hash_mismatch", verified=False)
    cache_path = cache / f"{METHOD}-{mode}-{digest}.json"
    # Cache is only derived observations; it never grants approval or substitutes
    # for checking source bytes. Invalid cache documents are explicit errors.
    if cache_path.exists():
        if cache_path.is_symlink():
            raise ValueError("symlink cache is not supported")
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if (not isinstance(cached, dict) or cached.get("method") != METHOD or
                cached.get("sha256") != digest or cached.get("mode") != mode or
                not isinstance(cached.get("result"), dict) or
                cached["result"].get("verified") is not True or
                not isinstance(cached["result"].get("observations"), list) or
                not isinstance(cached["result"].get("status"), str)):
            raise ValueError("inspection cache identity mismatch")
        return cached["result"]
    result = dict(inspect_bytes(data, mode), verified=True)
    cache.mkdir(parents=True, exist_ok=True)
    document = dict(method=METHOD, mode=mode, sha256=digest, result=result)
    try:
        write_manifest(document, cache_path)
    except FileExistsError:
        if json.loads(cache_path.read_text(encoding="utf-8")) != document:
            raise ValueError("conflicting inspection cache")
    return result


def inspect_manifest(manifest_path, source_root, cache_root, *, nearby_text=False):
    raw = Path(manifest_path).read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in ("0.9", "kcd-director-experimental-1"):
        raise ValueError("unsupported ingest schema")
    if not isinstance(manifest.get("entries"), list) or not isinstance(manifest.get("file_inventory"), list):
        raise ValueError("manifest entries and file inventory must be arrays")
    root, cache = Path(source_root).resolve(), Path(cache_root).resolve()
    if cache == root or root in cache.parents:
        raise ValueError("cache must be outside source media")
    inventory = {}
    for item in manifest["file_inventory"]:
        if not isinstance(item, dict):
            raise ValueError("invalid file inventory item")
        path = item["path"]
        if (not isinstance(path, str) or path in inventory or
                not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) or
                not isinstance(item.get("size"), int) or isinstance(item["size"], bool) or item["size"] < 0):
            raise ValueError("invalid or duplicate file inventory item")
        inventory[path] = item
    manifest_ref = "sha256:" + hashlib.sha256(raw).hexdigest()
    entries, files, seen = [], {}, set()
    requested_bytes = 0
    for entry in manifest["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("files"), dict) or not isinstance(entry.get("normalized"), dict):
            raise ValueError("invalid source entry")
        source_id = entry["source_id"]
        if not isinstance(source_id, str) or not source_id or source_id in seen:
            raise ValueError("invalid or duplicate entry")
        seen.add(source_id)
        refs = entry["files"]["inventory_refs"]
        if not isinstance(refs, list) or any(not isinstance(p, str) or p not in inventory for p in refs):
            raise ValueError("unobserved file reference")
        selected = {p: "explicit_reference" for p in refs}
        parents = {str(PurePosixPath(p).parent) for p in refs}
        nearby = sorted(p for p in inventory if p not in selected and
                        PurePosixPath(p).suffix.lower() in TEXT_SUFFIXES and
                        str(PurePosixPath(p).parent) in parents) if nearby_text else []
        for path in nearby[:MAX_NEARBY]:
            selected[path] = "adjacent_text_hint"
        entry_files = []
        for path, association in selected.items():
            item = inventory[path]
            if path not in files:
                if requested_bytes + item["size"] > MAX_TOTAL:
                    result = _result("run_size_limit", verified=False)
                else:
                    requested_bytes += item["size"]
                    result = inspect_file(root, item, cache)
                files[path] = dict(path=path, sha256=item["sha256"], size=item["size"],
                                   **result)
            entry_files.append(dict(path=path, association=association))
        entries.append(dict(key=dict(manifest=manifest_ref, entry=source_id),
                            source_title=entry["normalized"].get("title"), files=entry_files,
                            nearby_text_omitted=max(0, len(nearby) - MAX_NEARBY),
                            source_issues=entry.get("issues", [])))
    return dict(schema="bootdisk-file-inspection-1", method=METHOD, manifest=manifest_ref,
                scope="file observations, not software identity or edition decisions",
                selection=dict(nearby_text=nearby_text, nearby_limit=MAX_NEARBY,
                               max_file_bytes=MAX_FILE, max_text_bytes=MAX_TEXT, max_run_bytes=MAX_TOTAL),
                entries=entries, files=list(files.values()),
                summary=dict(entries=len(entries), files=len(files),
                             outcomes=dict(sorted(Counter(f["status"] for f in files.values()).items()))))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect preserved file metadata without executing programs")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--nearby-text", action="store_true", help="include adjacent text as hints, never product identity")
    args = parser.parse_args(argv)
    try:
        source, output = args.source.resolve(), args.output.resolve()
        if output == source or source in output.parents:
            raise ValueError("output must be outside source media")
        report = inspect_manifest(args.manifest, source, args.cache, nearby_text=args.nearby_text)
        write_manifest(report, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"inspection failed: {exc}\n")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
