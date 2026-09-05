import json

from .config import KNOWN_ASSETS


def write_manifest(
    manifest,
    output_file,
):
    output_file.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def print_report(
    manifest,
    output_file,
):
    entries = manifest["entries"]
    stats = manifest["statistics"]
    validation = manifest["validation"]
    media = manifest.get("media", {})

    print()
    print("Bootdisk ingest v0.8.0")
    print("=" * 40)
    print(f"Fant {len(entries)} poster")
    print()

    missing_refs = validation[
        "missing_referenced_files"
    ]

    print(
        "Refererte filer som ikke finnes: "
        f"{len(missing_refs)}"
    )

    if missing_refs:
        for item in missing_refs:
            print(
                f"  {item['source_id']}: "
                f"{item['title']} | "
                f"{item['type']} | "
                f"{item['path']}"
            )

    print()
    print("Oppdagede ressurser:")

    assets = stats[
        "discovered_assets"
    ]

    for asset_type in KNOWN_ASSETS:
        found = assets.get(
            f"{asset_type}_found",
            0,
        )
        total = assets.get(
            f"{asset_type}_total",
            0,
        )

        print(
            f"  {asset_type:16} "
            f"{found}/{total}"
        )

    print()
    print(
        "Case-insensitive path-treff: "
        f"{stats['path_resolution']['case_insensitive_matches']}"
    )

    print()
    print(
        "CPU=42 tolket som ukjent krav: "
        f"{stats['cpu_42_placeholder_count']} "
        "poster"
    )

    print()
    print("Globalt filinventar:")

    disc_stats = stats[
        "disc_inventory"
    ]

    print(
        f"  Fysiske filer:             "
        f"{disc_stats['physical_files']}"
    )
    print(
        f"  Totalt bytes:              "
        f"{disc_stats['total_bytes']}"
    )
    print(
        f"  Unike SHA-256:             "
        f"{disc_stats['unique_sha256']}"
    )
    print(
        f"  Duplikatforekomster:       "
        f"{disc_stats['duplicate_hash_occurrences']}"
    )

    disc_identity = manifest["disc"]["content_identity"]

    print()
    print("Disc content identity:")
    print(
        f"  Filer:                     "
        f"{disc_identity['file_count']}"
    )
    print(
        f"  Totalt bytes:              "
        f"{disc_identity['total_size']}"
    )
    print(
        f"  Manifest SHA-256:          "
        f"{disc_identity['manifest_sha256']}"
    )

    print()
    print("Entry-referanser:")

    entry_stats = stats[
        "entry_inventory"
    ]

    print(
        f"  Filreferanser:             "
        f"{entry_stats['file_references']}"
    )
    print(
        f"  Bytes på tvers av entries: "
        f"{entry_stats['total_bytes_across_entries']}"
    )

    print()
    print("Medieidentitet:")

    if media.get("available"):
        print(
            f"  Format:                    "
            f"{media['format']}"
        )
        print(
            f"  Størrelse:                 "
            f"{media['size']}"
        )
        print(
            f"  SHA-256:                   "
            f"{media['sha256']}"
        )
        print(
            f"  Media ID:                  "
            f"{media['media_id']}"
        )
    else:
        print(
            "  Ingen image-fil oppgitt."
        )

    print()
    print("Filsystem:")

    filesystem = manifest["disc"].get("filesystem", {})

    if filesystem.get("available") and filesystem.get("iso9660"):
        print("  Type:                      iso9660")
        primary = filesystem.get("primary_volume_descriptor")

        if primary is not None:
            print(
                f"  Volume ID:                 "
                f"{primary['volume_id']}"
            )
            print(
                f"  System ID:                 "
                f"{primary['system_id']}"
            )

            block_size = primary["logical_block_size"]
            print(
                f"  Logical block size:        "
                f"{block_size['value']}"
            )

            volume_blocks = primary["volume_space_size_blocks"]
            print(
                f"  Volume blocks:             "
                f"{volume_blocks['value']}"
            )

        joliet = filesystem.get("joliet", {})
        print(
            f"  Joliet:                    "
            f"{'ja' if joliet.get('present') else 'nei'}"
        )

        if joliet.get("present"):
            levels = sorted(
                {item["level"] for item in joliet["descriptors"]}
            )
            print(
                f"  Joliet level:              "
                + ", ".join(str(level) for level in levels)
            )

        mismatches = filesystem.get(
            "numeric_endianness_mismatches", []
        )
        print(
            f"  Endian-avvik:              "
            f"{len(mismatches)}"
        )
    elif filesystem.get("available"):
        print("  ISO9660 ikke funnet.")
    else:
        print("  Ingen image-fil oppgitt.")

    print()
    print("Kategorier:")

    for category, count in (
        stats["categories"].items()
    ):
        print(
            f"  {category:16} {count}"
        )

    print()
    print("K.DTX SHA-256:")
    print(
        "  "
        + manifest["source"]["dtx_file"][
            "sha256"
        ]
    )

    print()
    print(f"Skrev {output_file}")
