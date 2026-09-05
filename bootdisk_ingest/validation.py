def build_validation(entries):
    warnings = []
    referenced_missing = []
    discovered_missing = []

    for entry in entries:
        source_id = entry["source_id"]
        title = entry["normalized"]["title"]

        for file_type, info in entry["files"]["referenced"].items():
            if not info.get("exists"):
                referenced_missing.append({
                    "source_id": source_id,
                    "title": title,
                    "type": file_type,
                    "path": info["path"],
                })

        for asset_type, info in entry["files"]["discovered"].items():
            if not info.get("exists"):
                discovered_missing.append({
                    "source_id": source_id,
                    "title": title,
                    "type": asset_type,
                    "path": info["path"],
                })

    if referenced_missing:
        warnings.append(
            f"{len(referenced_missing)} explicitly referenced files are missing"
        )

    return {
        "valid": len(referenced_missing) == 0,
        "warnings": warnings,
        "missing_referenced_files": referenced_missing,
        "missing_discovered_assets": discovered_missing,
    }
