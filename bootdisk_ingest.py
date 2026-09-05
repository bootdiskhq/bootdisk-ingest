import argparse
from pathlib import Path

from bootdisk_ingest.inventory import build_disc_inventory
from bootdisk_ingest.media import build_media_metadata
from bootdisk_ingest.iso9660 import inspect_iso9660
from bootdisk_ingest.parser_kcd_dtx_v1 import parse_disc
from bootdisk_ingest.stats import build_statistics
from bootdisk_ingest.validation import build_validation
from bootdisk_ingest.output import write_manifest, print_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bootdisk ingest"
    )

    parser.add_argument(
        "disc_root",
        nargs="?",
        default=".",
        help=(
            "Path to mounted disc root. "
            "Defaults to current directory."
        ),
    )

    parser.add_argument(
        "--image",
        type=Path,
        help=(
            "Path to original disc image, e.g. ISO. "
            "Used for media identity and hashing."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    disc_root = Path(args.disc_root).resolve()
    output_file = Path(__file__).resolve().parent / "manifest.json"

    disc_inventory = build_disc_inventory(
        disc_root
    )

    manifest = parse_disc(
        disc_root,
        disc_inventory,
    )

    manifest["media"] = build_media_metadata(
        args.image
    )

    manifest["disc"]["filesystem"] = inspect_iso9660(
        args.image
    )

    manifest["file_inventory"] = (
        disc_inventory["files"]
    )

    manifest["statistics"] = (
        build_statistics(
            manifest["entries"],
            disc_inventory,
        )
    )

    manifest["validation"] = (
        build_validation(
            manifest["entries"]
        )
    )

    write_manifest(
        manifest,
        output_file,
    )

    print_report(
        manifest,
        output_file,
    )


if __name__ == "__main__":
    main()
