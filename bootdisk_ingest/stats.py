from collections import Counter


def build_statistics(entries):
    key_occurrences = Counter()
    key_values = Counter()
    category_occurrences = Counter()
    referenced_file_stats = Counter()
    discovered_asset_stats = Counter()

    cpu_placeholder_count = 0
    total_inventory_files = 0
    total_inventory_bytes = 0

    for entry in entries:
        raw = entry["raw"]

        for key, value in raw.items():
            key_occurrences[key] += 1
            if value.strip():
                key_values[key] += 1

        for category in entry["normalized"]["categories"]:
            category_occurrences[category] += 1

        cpu = entry["normalized"]["requirements"]["cpu"]
        if cpu["interpretation"] == "editorial_placeholder_unknown":
            cpu_placeholder_count += 1

        for file_type, info in entry["files"]["referenced"].items():
            referenced_file_stats[f"{file_type}_total"] += 1
            if info.get("exists"):
                referenced_file_stats[f"{file_type}_found"] += 1

        for asset_type, info in entry["files"]["discovered"].items():
            discovered_asset_stats[f"{asset_type}_total"] += 1
            if info.get("exists"):
                discovered_asset_stats[f"{asset_type}_found"] += 1

        identity = entry["content_identity"]
        total_inventory_files += identity["file_count"]
        total_inventory_bytes += identity["total_size"]

    fields = {}

    for key in sorted(
        key_occurrences.keys(),
        key=lambda key: (-key_occurrences[key], key),
    ):
        fields[key] = {
            "present": key_occurrences[key],
            "with_value": key_values[key],
        }

    return {
        "entry_count": len(entries),
        "fields": fields,
        "categories": dict(
            sorted(
                category_occurrences.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "cpu_42_placeholder_count": cpu_placeholder_count,
        "referenced_files": dict(referenced_file_stats),
        "discovered_assets": dict(discovered_asset_stats),
        "inventory": {
            "file_occurrences": total_inventory_files,
            "total_bytes": total_inventory_bytes,
        },
    }
