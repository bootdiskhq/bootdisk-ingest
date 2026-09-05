from pathlib import Path

from bootdisk_ingest.inventory import build_disc_inventory
from bootdisk_ingest.parser_kcd_dtx_v1 import parse_disc
from bootdisk_ingest.stats import build_statistics
from bootdisk_ingest.validation import build_validation
from bootdisk_ingest.output import write_manifest, print_report


def main():
    disc_root = Path.cwd()
    output_file = Path(__file__).resolve().parent / "manifest.json"

    disc_inventory = build_disc_inventory(disc_root)

    manifest = parse_disc(
        disc_root,
        disc_inventory,
    )

    manifest["file_inventory"] = disc_inventory["files"]
    manifest["statistics"] = build_statistics(
        manifest["entries"],
        disc_inventory,
    )
    manifest["validation"] = build_validation(
        manifest["entries"]
    )

    write_manifest(manifest, output_file)
    print_report(manifest, output_file)


if __name__ == "__main__":
    main()
