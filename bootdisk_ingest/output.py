import json

from .config import KNOWN_ASSETS


def write_manifest(manifest, output_file):
    output_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_report(manifest, output_file):
    entries = manifest["entries"]
    stats = manifest["statistics"]
    validation = manifest["validation"]

    print()
    print("Bootdisk ingest v0.4.1")
    print("=" * 40)
    print(f"Fant {len(entries)} poster")
    print()

    missing_refs = validation["missing_referenced_files"]

    print(f"Refererte filer som ikke finnes: {len(missing_refs)}")

    if missing_refs:
        for item in missing_refs:
            print(
                f"  {item['source_id']}: {item['title']} | "
                f"{item['type']} | {item['path']}"
            )

    print()
    print("Oppdagede ressurser:")

    assets = stats["discovered_assets"]

    for asset_type in KNOWN_ASSETS:
        found = assets.get(f"{asset_type}_found", 0)
        total = assets.get(f"{asset_type}_total", 0)
        print(f"  {asset_type:16} {found}/{total}")

    print()
    print(
        "CPU=42 tolket som ukjent krav: "
        f"{stats['cpu_42_placeholder_count']} poster"
    )

    print()
    print("Filinventar:")

    inventory = stats["inventory"]

    print(f"  Filforekomster: {inventory['file_occurrences']}")
    print(f"  Totalt bytes:    {inventory['total_bytes']}")

    print()
    print("Kategorier:")

    for category, count in stats["categories"].items():
        print(f"  {category:16} {count}")

    print()
    print("K.DTX SHA-256:")
    print("  " + manifest["source"]["dtx_file"]["sha256"])

    print()
    print(f"Skrev {output_file}")
