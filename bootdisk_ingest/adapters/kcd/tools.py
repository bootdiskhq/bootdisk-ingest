"""Observe the supplementary Tools.dtx catalogue without inventing K.DTX fields."""
import base64
import configparser
import hashlib
from pathlib import Path, PurePosixPath
import re

from bootdisk_ingest.inventory import get_file_record


def parse_tools(disc_root, inventory):
    from .parser import build_entry
    metadata = get_file_record(inventory, "Tools.dtx")
    if not metadata.get("exists"):
        return [], None
    relative = metadata.get("resolved_path", "Tools.dtx")
    path = Path(disc_root) / relative
    if not path.resolve().is_relative_to(Path(disc_root).resolve()):
        raise ValueError("Tools.dtx escapes media")
    raw = path.read_bytes()
    if len(raw) != metadata["size"] or hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("Tools.dtx changed after inventory; ingest a stable source")
    warnings = []
    try:
        text = raw.decode("cp1252")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
        warnings.append("Undefined CP1252 bytes replaced; original bytes retained")
    # Preserve duplicates in the raw bytes and warn about the lossy INI view,
    # using the same explicit last-value-wins policy as K.DTX.
    strict = configparser.ConfigParser(interpolation=None)
    strict.optionxform = str
    try:
        strict.read_string(text)
    except (configparser.DuplicateSectionError, configparser.DuplicateOptionError):
        warnings.append("Duplicate INI fields or sections; parsed view uses the last value")
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    config.read_string(text)
    entries, skipped = [], []
    for section in config.sections():
        if not re.fullmatch(r"I[0-9]+", section):
            skipped.append(section)
            continue
        values = dict(config[section])
        if not values.get("Navn", "").strip() or not values.get("Folder", "").strip():
            raise ValueError(f"Tools.dtx [{section}] lacks Navn or Folder")
        for field in ("Folder", "Setup", "Run"):
            value = values.get(field, "").strip().replace("\\", "/")
            parts = PurePosixPath(value)
            if value and (parts.is_absolute() or ".." in parts.parts or ":" in value or value == "."):
                raise ValueError(f"Tools.dtx [{section}] has unsafe {field}")
        # Reuse file observation and identity rules, then retain the actual raw
        # fields (Navn/InstruksNo), never fabricated Titel/Global in source data.
        projected = {k: values[k] for k in ("Folder", "Setup", "Run", "Licens", "Websted") if k in values}
        projected.update(Titel=values["Navn"], Global=values.get("InstruksNo", ""))
        entry = build_entry(inventory, section, projected)
        entry["raw"] = values
        # The Tools Ja flags include Spil on AdAware. They are not K.DTX category
        # semantics; retain flags and numeric categories raw, but never map them.
        entry["normalized"]["categories"] = []
        entry["evidence"] = {"metadata_source": {"path": relative, "sha256": metadata["sha256"], "section": section},
                             "description_tools": {"path": relative, "sha256": metadata["sha256"],
                                 "section": section, "field": "InstruksNo", "language": "nb-NO",
                                 "text": values.get("InstruksNo")}}
        entry["interpretations"]["tools_projection"] = {
            "method": "tools-dtx-norwegian-1", "title_field": "Navn", "description_field": "InstruksNo",
            "category_policy": "Tools flags and Kategori numbers are retained raw, not mapped to content kind"}
        entries.append(entry)
    document = {"path": "Tools.dtx", "resolved_path": relative, "encoding": "cp1252",
                "size": len(raw), "sha256": metadata["sha256"], "raw_base64": base64.b64encode(raw).decode("ascii"),
                "sections": {s: dict(config[s]) for s in config.sections()}, "defaults": dict(config.defaults()),
                "parser_warnings": warnings, "projected_entry_ids": [e["source_id"] for e in entries],
                "unprojected_sections": skipped}
    return entries, document


def metadata_coverage(inventory, primary_sections, primary_ids, tools, entries):
    processed = ["K.DTX"] + ([tools["resolved_path"]] if tools else [])
    unknown = [f["path"] for f in inventory["files"]
               if f["path"].lower().endswith(".dtx") and f["path"].casefold() not in {p.casefold() for p in processed}]
    primary_skipped = [s for s in primary_sections if s != "Generelt" and s not in primary_ids]
    sections = [{"path": "K.DTX", "projected_entry_ids": primary_ids, "unprojected_sections": primary_skipped}]
    if tools:
        sections.append({"path": tools["resolved_path"], "projected_entry_ids": tools["projected_entry_ids"],
                         "unprojected_sections": tools["unprojected_sections"]})
    folders = {}
    for entry in entries:
        folder = entry["normalized"]["folder"]
        if folder:
            folders.setdefault(folder.casefold(), []).append(entry["source_id"])
    return {"scope": "Known DTX metadata only; not complete-disc or menu-reachability certification",
            "complete_disc": False,
            "unprocessed_metadata": unknown, "metadata_files": sections,
            "shared_entry_folders": [{"folder": folder, "entry_ids": ids, "meaning": "shared folder, not an identity decision"}
                                     for folder, ids in sorted(folders.items()) if len(ids) > 1]}
