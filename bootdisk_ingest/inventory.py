from pathlib import Path

from .hashing import sha256_file


def build_disc_inventory(disc_root):
    files = []

    paths = sorted(
        (p for p in disc_root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(disc_root).as_posix().lower(),
    )

    for path in paths:
        relative_path = path.relative_to(
            disc_root
        ).as_posix()

        files.append({
            "path": relative_path,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    by_path = {
        item["path"]: item
        for item in files
    }

    return {
        "files": files,
        "by_path": by_path,
    }


def get_file_record(disc_inventory, relative_path):
    if relative_path is None:
        return None

    item = disc_inventory["by_path"].get(
        relative_path
    )

    if item is None:
        return {
            "path": relative_path,
            "exists": False,
        }

    return {
        "path": item["path"],
        "exists": True,
        "is_file": True,
        "size": item["size"],
        "sha256": item["sha256"],
    }


def get_folder_records(disc_inventory, folder):
    if not folder:
        return []

    prefix = folder.rstrip("/") + "/"

    return [
        item
        for item in disc_inventory["files"]
        if (
            item["path"] == folder
            or item["path"].startswith(prefix)
        )
    ]
