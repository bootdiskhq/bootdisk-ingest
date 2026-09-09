"""Compatibility launcher; the installed and module CLIs share one entry point."""
from bootdisk_ingest.cli import main, parse_args

if __name__ == "__main__":
    raise SystemExit(main())
