import hashlib


def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def file_metadata(disc_root, relative_path):
    if relative_path is None:
        return None

    path = disc_root / relative_path

    if not path.exists():
        return {"path": relative_path, "exists": False}

    if not path.is_file():
        return {
            "path": relative_path,
            "exists": True,
            "is_file": False,
        }

    return {
        "path": relative_path,
        "exists": True,
        "is_file": True,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def inventory_folder(disc_root, folder):
    if not folder:
        return []

    folder_path = disc_root / folder
    if not folder_path.exists():
        return []

    files = []

    for path in sorted(
        (p for p in folder_path.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(disc_root).as_posix().lower(),
    ):
        relative_path = path.relative_to(disc_root).as_posix()
        files.append({
            "path": relative_path,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    return files


def build_content_identity(inventory):
    digest = hashlib.sha256()
    total_size = 0

    for item in sorted(inventory, key=lambda item: item["path"]):
        total_size += item["size"]
        record = item["path"] + "\0" + item["sha256"] + "\n"
        digest.update(record.encode("utf-8"))

    return {
        "algorithm": "sha256",
        "file_count": len(inventory),
        "total_size": total_size,
        "manifest_sha256": digest.hexdigest(),
    }
