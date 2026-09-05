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


def build_content_identity(file_records):
    digest = hashlib.sha256()
    total_size = 0

    sorted_records = sorted(
        file_records,
        key=lambda item: item["path"],
    )

    for item in sorted_records:
        total_size += item["size"]

        record = (
            item["path"]
            + "\0"
            + item["sha256"]
            + "\n"
        )

        digest.update(
            record.encode("utf-8")
        )

    return {
        "algorithm": "sha256",
        "file_count": len(sorted_records),
        "total_size": total_size,
        "manifest_sha256": digest.hexdigest(),
    }


def build_disc_content_identity(file_records):
    """Build a deterministic logical identity for the disc contents.

    The identity is based on the actual on-disc relative path and SHA-256
    of every physical file in the global inventory, sorted by path.
    It intentionally does not include local mount paths, timestamps,
    inode data, or the media-image hash.
    """
    return build_content_identity(file_records)
