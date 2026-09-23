"""Observe K-CD metadata while keeping interpretations separate from evidence.

The INI view is convenient but cannot preserve duplicates, comments or undecodable
bytes. The manifest therefore also carries the exact metadata bytes.
"""
import base64
import hashlib
from pathlib import Path
import configparser
from datetime import datetime, timezone

from bootdisk_ingest.config import (
    PARSER_VERSION,
    SCHEMA_VERSION,
)
from .config import KNOWN_ASSETS, KNOWN_NON_CATEGORY_FIELDS, SOURCE_FORMAT
from bootdisk_ingest.core.identity import build_content_identity
from bootdisk_ingest.formats.rtf import plain_text, METHOD as RTF_METHOD
from bootdisk_ingest.inventory import (
    get_file_record,
    get_folder_records,
)
from .paths import (
    normalize_string,
    normalize_windows_path,
    relative_disc_path,
)

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


def build_entry(
    disc_inventory,
    section_name,
    section,
):
    """Project editorial values without replacing their source evidence."""
    raw = dict(section)

    folder = normalize_windows_path(
        normalize_string(raw.get("Folder"))
    )
    setup = normalize_windows_path(
        normalize_string(raw.get("Setup"))
    )
    run = normalize_windows_path(
        normalize_string(raw.get("Run"))
    )

    setup_path = relative_disc_path(
        folder,
        setup,
    )
    run_path = relative_disc_path(
        folder,
        run,
    )

    referenced_files = {}

    if setup_path:
        referenced_files["installer"] = (
            get_file_record(
                disc_inventory,
                setup_path,
            )
        )

    if run_path:
        referenced_files["run"] = (
            get_file_record(
                disc_inventory,
                run_path,
            )
        )

    discovered_assets = {}

    for asset_type, filename in (
        KNOWN_ASSETS.items()
    ):
        asset_path = relative_disc_path(
            folder,
            filename,
        )

        # Earlier DTX discs also use Shot.bmp. Preserve the established JPG
        # convention when both exist; only fall back when JPG is absent.
        if asset_type == "screenshot" and not get_file_record(disc_inventory, asset_path).get("exists"):
            bitmap_path = relative_disc_path(folder, "Shot.bmp")
            if get_file_record(disc_inventory, bitmap_path).get("is_file"):
                asset_path = bitmap_path

        discovered_assets[asset_type] = (
            get_file_record(
                disc_inventory,
                asset_path,
            )
        )

    folder_records = get_folder_records(
        disc_inventory,
        folder,
    )

    normalized = {
        "title": normalize_string(
            raw.get("Titel")
        ),
        "short_title": normalize_string(
            raw.get("KortTitel")
        ),
        "description": normalize_string(
            raw.get("Global")
        ),
        "folder": folder,
        "installer": setup_path,
        "run": run_path,
        "license": normalize_string(
            raw.get("Licens")
        ),
        "website": normalize_string(
            raw.get("Websted")
        ),
        "requirements": {
            "cpu": normalize_cpu(
                raw.get("CPU")
            ),
            "ram_mb": parse_int(
                raw.get("Ram")
            ),
            "disk_mb": parse_int(
                raw.get("HD")
            ),
            "directx": normalize_string(
                raw.get("DX")
            ),
        },
        "requires_network": normalize_string(
            raw.get("Net")
        ),
        "categories": extract_categories(raw),
    }

    interpretations = {}

    if raw.get("CPU", "").strip() == "42":
        interpretations["CPU"] = {
            "raw_value": "42",
            "meaning": "unknown",
            "confidence": "interpreted",
            "note": (
                "K-CD appears to use 42 as an editorial "
                "placeholder for an unknown CPU requirement, "
                "likely referencing The Hitchhiker's Guide "
                "to the Galaxy."
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
            "inventory_refs": [
                item["path"]
                for item in folder_records
            ],
        },
        "content_identity": (
            build_content_identity(
                folder_records
            )
        ),
    }


def build_source_metadata(
    disc_inventory,
):
    metadata = get_file_record(
        disc_inventory,
        "K.DTX",
    )

    return {
        "format": SOURCE_FORMAT,
        "dtx_file": {
            "path": "K.DTX",
            "encoding": "cp1252",
            "size": metadata.get("size"),
            "sha256": metadata.get("sha256"),
        },
    }


def parse_disc(
    disc_root,
    disc_inventory,
    *,
    generated_at=None,
):
    disc_root = Path(disc_root)
    metadata = get_file_record(disc_inventory, "K.DTX")
    dtx_file = disc_root / metadata.get("resolved_path", "K.DTX")

    if not metadata.get("exists"):
        raise ValueError("K.DTX is missing from the source inventory")
    raw_bytes = dtx_file.read_bytes()
    if len(raw_bytes) != metadata["size"] or hashlib.sha256(raw_bytes).hexdigest() != metadata["sha256"]:
        raise ValueError("K.DTX changed after inventory; ingest a stable source")

    warnings = []
    try:
        text = raw_bytes.decode("cp1252")
    except UnicodeDecodeError:
        text = raw_bytes.decode("cp1252", errors="replace")
        warnings.append("Undefined CP1252 bytes replaced in parsed view; original bytes retained")

    # Retain the historical last-value-wins INI projection, but make loss in
    # that projection explicit and keep byte-level evidence for future parsers.
    probe = configparser.ConfigParser(interpolation=None)
    probe.optionxform = str
    try:
        probe.read_string(text)
    except (configparser.DuplicateSectionError, configparser.DuplicateOptionError):
        warnings.append("Duplicate INI fields or sections; parsed view uses the last value")
    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.optionxform = str
    config.read_string(text)

    disc_raw = (
        dict(config["Generelt"])
        if config.has_section("Generelt")
        else {}
    )

    entries = []

    for section_name in config.sections():
        if section_name == "Generelt":
            continue

        if section_name.startswith("K"):
            entries.append(
                build_entry(
                    disc_inventory,
                    section_name,
                    config[section_name],
                )
            )

    for entry in entries:
        if (entry.get("raw", {}).get("Global") or "").strip():
            continue
        rtf = entry["files"]["discovered"].get("description_rtf", {})
        if not rtf.get("is_file"):
            continue
        relative = rtf.get("resolved_path", rtf["path"])
        path = (disc_root / relative).resolve()
        if not path.is_relative_to(disc_root.resolve()):
            raise ValueError("RTF source escapes media")
        if rtf["size"] > 1024 * 1024:
            warnings.append(f"{entry['source_id']}: RTF description exceeds observation limit")
            continue
        data = path.read_bytes()
        if len(data) != rtf["size"] or hashlib.sha256(data).hexdigest() != rtf["sha256"]:
            raise ValueError("RTF changed after inventory")
        observation = {"path": relative, "sha256": rtf["sha256"], "size": len(data),
                       "raw_base64": base64.b64encode(data).decode("ascii"), "method": RTF_METHOD}
        try:
            observation["text"] = plain_text(data)
        except (ValueError, UnicodeError) as exc:
            observation["text"] = None
            observation["warning"] = str(exc)
            warnings.append(f"{entry['source_id']}: RTF description not decoded: {exc}")
        entry.setdefault("evidence", {})["description_rtf"] = observation

    source = build_source_metadata(disc_inventory)
    source["dtx_file"]["raw_base64"] = base64.b64encode(raw_bytes).decode("ascii")
    if metadata.get("resolved_path"):
        source["dtx_file"]["resolved_path"] = metadata["resolved_path"]
    source["parser_warnings"] = warnings
    source["sections"] = {name: dict(config[name]) for name in config.sections()}
    source["defaults"] = dict(config.defaults())
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "name": "bootdisk-ingest",
            "version": PARSER_VERSION,
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        },
        "source": source,
        "disc": {
            "raw": disc_raw,
            "content_identity": build_content_identity(
                disc_inventory["files"]
            ),
        },
        "entries": entries,
    }
