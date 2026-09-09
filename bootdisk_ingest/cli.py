"""Command-line policy stays outside the parser and preservation core."""
import argparse
import configparser
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

from . import __version__
from .output import print_report, write_manifest
from .pipeline import ingest_kcd


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Observe K-CD source files without modifying them")
    parser.add_argument("source_root", nargs="?", default=".", type=Path)
    parser.add_argument("--image", type=Path, help="Original image, independently hashed")
    parser.add_argument("--output", type=Path, default=Path("ingest-manifest.json"),
                        help="Manifest outside the source tree (default: ./ingest-manifest.json)")
    parser.add_argument("--force", action="store_true", help="Replace an existing output atomically")
    parser.add_argument("--strict", action="store_true", help="Return 1 after writing if referenced files are missing")
    parser.add_argument("--quiet", action="store_true", help="Suppress the human-readable report")
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        root = args.source_root.expanduser().resolve()
        output = args.output.expanduser().absolute()
        resolved_output = output.resolve()
        if resolved_output.is_relative_to(root):
            raise ValueError("Output must be outside the source tree")
        if output.is_symlink():
            raise ValueError("Output must not be a symbolic link")
        if args.image and resolved_output == args.image.expanduser().resolve():
            raise ValueError("Output must not replace the original image")
        if output.exists() and not args.force:
            raise ValueError("Output already exists; use --force to replace it")
        generated_at = None
        if "SOURCE_DATE_EPOCH" in os.environ:
            generated_at = datetime.fromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]), timezone.utc).isoformat()
        manifest = ingest_kcd(root, image=args.image, generated_at=generated_at)
        write_manifest(manifest, output, overwrite=args.force)
        if not args.quiet:
            print_report(manifest, output)
        return 1 if args.strict and not manifest["validation"]["valid"] else 0
    except (OSError, ValueError, OverflowError, configparser.Error) as error:
        print(f"bootdisk-ingest: {error}", file=sys.stderr)
        return 2
