import configparser
from datetime import datetime, timezone

from .config import (
    KNOWN_ASSETS,
    KNOWN_NON_CATEGORY_FIELDS,
    PARSER_VERSION,
    SCHEMA_VERSION,
    SOURCE_FORMAT,
)
from .hashing import build_content_identity, file_metadata, inventory_folder
from .paths import normalize_string, normalize_windows_path, relative_disc_path


def parse_int(value):
    value = normalize_string(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def normalize_cpu(raw_value):
    value = parse_int(raw_value)

    if value == 42:
        return {
            "mhz": None,
            "source_value": 42,
            "known": False,
            "interpretation": "editorial_placeholder_unknown",
        }

    if value is None:
        return {
            "mhz": None,
            "source_value": normalize_string(raw_value),
            "known": False,
            "interpretation": None,
        }

    return {
        "mhz": value,
        "source_value": value,
        "known": True,
        "interpretation": None,
    }


def extract_categories(raw):
    categories = []

    for key, value in raw.items():
        if key in KNOWN_NON_CATEGORY_FIELDS:
            continue
        if value.strip().lower() == "ja":
            categories.append(key)

    return categories


def build_entry(disc_root, section_name, section):
    raw = dict(section)

    folder = normalize_windows_path(normalize_string(raw.get("Folder")))
    setup = normalize_windows_path(normalize_string(raw.get("Setup")))
    run = normalize_windows_path(normalize_string(raw.get("Run")))

    setup_path = relative_disc_path(folder, setup)
    run_path = relative_disc_path(folder, run)

    referenced_files = {}

    if setup_path:
        referenced_files["installer"] = file_metadata(disc_root, setup_path)

    if run_path:
        referenced_files["run"] = file_metadata(disc_root, run_path)

    discovered_assets = {}

    for asset_type, filename in KNOWN_ASSETS.items():
        asset_path = relative_disc_path(folder, filename)
        discovered_assets[asset_type] = file_metadata(disc_root, asset_path)

    inventory = inventory_folder(disc_root, folder)

    normalized = {
        "title": normalize_string(raw.get("Titel")),
        "short_title": normalize_string(raw.get("KortTitel")),
        "description": normalize_string(raw.get("Global")),
        "folder": folder,
        "installer": setup_path,
        "run": run_path,
        "license": normalize_string(raw.get("Licens")),
        "website": normalize_string(raw.get("Websted")),
        "requirements": {
            "cpu": normalize_cpu(raw.get("CPU")),
            "ram_mb": parse_int(raw.get("Ram")),
            "disk_mb": parse_int(raw.get("HD")),
            "directx": normalize_string(raw.get("DX")),
        },
        "requires_network": normalize_string(raw.get("Net")),
        "categories": extract_categories(raw),
    }

    interpretations = {}

    if raw.get("CPU", "").strip() == "42":
        interpretations["CPU"] = {
            "raw_value": "42",
            "meaning": "unknown",
            "confidence": "interpreted",
            "note": (
                "K-CD appears to use 42 as an editorial placeholder for an "
                "unknown CPU requirement, likely referencing The Hitchhiker's "
                "Guide to the Galaxy."
            ),
        }

    return {
        "source_id": section_name,
        "raw": raw,
        "normalized": normalized,
        "interpretations": interpretations,
        "files": {
            "referenced": referenced_files,
            "discovered": discovered_assets,
            "inventory": inventory,
        },
        "content_identity": build_content_identity(inventory),
    }


def build_source_metadata(disc_root):
    metadata = file_metadata(disc_root, "K.DTX")

    return {
        "format": SOURCE_FORMAT,
        "dtx_file": {
            "path": "K.DTX",
            "encoding": "cp1252",
            "size": metadata.get("size"),
            "sha256": metadata.get("sha256"),
        },
    }


def parse_disc(disc_root):
    dtx_file = disc_root / "K.DTX"

    if not dtx_file.exists():
        raise SystemExit(
            f"Fant ikke {dtx_file}\n"
            "Kjør scriptet fra roten av den monterte K-CD-en."
        )

    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.optionxform = str

    text = dtx_file.read_text(encoding="cp1252", errors="replace")
    config.read_string(text)

    disc_raw = dict(config["Generelt"]) if config.has_section("Generelt") else {}

    entries = []

    for section_name in config.sections():
        if section_name == "Generelt":
            continue
        if section_name.startswith("K"):
            entries.append(
                build_entry(disc_root, section_name, config[section_name])
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "name": "bootdisk-ingest",
            "version": PARSER_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "source": build_source_metadata(disc_root),
        "disc": {"raw": disc_raw},
        "entries": entries,
    }
