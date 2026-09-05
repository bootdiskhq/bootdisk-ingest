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

    by_casefold_path = {}

    for item in files:
        key = item["path"].casefold()

        if key not in by_casefold_path:
            by_casefold_path[key] = item

    return {
        "files": files,
        "by_path": by_path,
        "by_casefold_path": by_casefold_path,
    }


def get_file_record(disc_inventory, relative_path):
    if relative_path is None:
        return None

    item = disc_inventory[
        "by_path"
    ].get(relative_path)

    matched_case_insensitively = False

    if item is None:
        item = disc_inventory[
            "by_casefold_path"
        ].get(
            relative_path.casefold()
        )

        if item is not None:
            matched_case_insensitively = True

    if item is None:
        return {
            "path": relative_path,
            "exists": False,
        }

    result = {
        "path": relative_path,
        "exists": True,
        "is_file": True,
        "size": item["size"],
        "sha256": item["sha256"],
    }

    if matched_case_insensitively:
        result["resolved_path"] = item["path"]
        result["path_case_mismatch"] = True

    return result


def get_folder_records(disc_inventory, folder):
    if not folder:
        return []

    exact_prefix = folder.rstrip("/") + "/"

    exact_matches = [
        item
        for item in disc_inventory["files"]
        if (
            item["path"] == folder
            or item["path"].startswith(
                exact_prefix
            )
        )
    ]

    if exact_matches:
        return exact_matches

    folded_folder = folder.casefold()
    folded_prefix = (
        folded_folder.rstrip("/")
        + "/"
    )

    return [
        item
        for item in disc_inventory["files"]
        if (
            item["path"].casefold()
            == folded_folder
            or item["path"]
            .casefold()
            .startswith(folded_prefix)
        )
    ]
