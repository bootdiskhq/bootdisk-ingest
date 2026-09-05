from collections import Counter


def build_statistics(
    entries,
    disc_inventory,
):
    key_occurrences = Counter()
    key_values = Counter()
    category_occurrences = Counter()
    referenced_file_stats = Counter()
    discovered_asset_stats = Counter()

    cpu_placeholder_count = 0
    entry_file_references = 0
    entry_total_bytes = 0

    for entry in entries:
        raw = entry["raw"]

        for key, value in raw.items():
            key_occurrences[key] += 1

            if value.strip():
                key_values[key] += 1

        for category in (
            entry["normalized"]["categories"]
        ):
            category_occurrences[
                category
            ] += 1

        cpu = (
            entry["normalized"]
            ["requirements"]["cpu"]
        )

        if (
            cpu["interpretation"]
            == "editorial_placeholder_unknown"
        ):
            cpu_placeholder_count += 1

        for file_type, info in (
            entry["files"]["referenced"].items()
        ):
            referenced_file_stats[
                f"{file_type}_total"
            ] += 1

            if info.get("exists"):
                referenced_file_stats[
                    f"{file_type}_found"
                ] += 1

        for asset_type, info in (
            entry["files"]["discovered"].items()
        ):
            discovered_asset_stats[
                f"{asset_type}_total"
            ] += 1

            if info.get("exists"):
                discovered_asset_stats[
                    f"{asset_type}_found"
                ] += 1

        identity = entry["content_identity"]

        entry_file_references += (
            identity["file_count"]
        )
        entry_total_bytes += (
            identity["total_size"]
        )

    fields = {}

    for key in sorted(
        key_occurrences.keys(),
        key=lambda key: (
            -key_occurrences[key],
            key,
        ),
    ):
        fields[key] = {
            "present": key_occurrences[key],
            "with_value": key_values[key],
        }

    global_files = disc_inventory["files"]

    unique_hashes = {
        item["sha256"]
        for item in global_files
    }

    duplicate_hash_occurrences = (
        len(global_files)
        - len(unique_hashes)
    )

    return {
        "entry_count": len(entries),
        "fields": fields,
        "categories": dict(
            sorted(
                category_occurrences.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        ),
        "cpu_42_placeholder_count":
            cpu_placeholder_count,
        "referenced_files":
            dict(referenced_file_stats),
        "discovered_assets":
            dict(discovered_asset_stats),
        "entry_inventory": {
            "file_references":
                entry_file_references,
            "total_bytes_across_entries":
                entry_total_bytes,
        },
        "disc_inventory": {
            "physical_files":
                len(global_files),
            "total_bytes":
                sum(
                    item["size"]
                    for item in global_files
                ),
            "unique_sha256":
                len(unique_hashes),
            "duplicate_hash_occurrences":
                duplicate_hash_occurrences,
        },
    }
