"""Stable identity helpers."""
import re
import hashlib

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def artifact_id_from_sha256(digest: str) -> str:
    normalized = digest.strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError("Expected a 64-character hexadecimal SHA-256 digest")
    return f"sha256:{normalized}"

def _field(record, name):
    if isinstance(record, dict):
        return record[name]

    return getattr(record, name)

def build_content_identity(file_records):
    """Hash sorted UTF-8 path/NUL/digest/newline records (legacy contract).

    Size is reported but intentionally excluded from the digest. Never change
    this framing without a separately versioned identity algorithm.
    """
    digest = hashlib.sha256()
    total_size = 0

    sorted_records = sorted(
        file_records,
        key=lambda item: _field(item, "path"),
     )

    for item in sorted_records:
        path = _field(item, "path")
        size = _field(item, "size")
        sha256 = _field(item, "sha256")

        total_size += size

        record = (
            path
            + "\0"
            + sha256
            + "\n"
        )

        digest.update(record.encode("utf-8"))


    return {
        "algorithm": "sha256",
        "file_count": len(sorted_records),
        "total_size": total_size,
        "manifest_sha256": digest.hexdigest(),
    }
