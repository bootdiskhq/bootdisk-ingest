"""Compatibility imports for the original K-CD parser module."""
from .adapters.kcd.parser import (
    build_entry, build_source_metadata, extract_categories,
    normalize_cpu, parse_disc, parse_int,
)

__all__ = ["build_entry", "build_source_metadata", "extract_categories",
           "normalize_cpu", "parse_disc", "parse_int"]
