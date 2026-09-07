"""Source-agnostic Bootdisk core domain entities."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class KnowledgeKind(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INTERPRETED = "interpreted"
    CURATED = "curated"


@dataclass(slots=True)
class Source:
    source_id: str | None = None
    source_type: str | None = None
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Collection:
    collection_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Media:
    media_id: str | None = None
    media_type: str | None = None
    format: str | None = None
    sha256: str | None = None
    size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Entry:
    """A source-defined editorial/catalog entry. Not every source has one."""
    entry_id: str | None = None
    source_entry_id: str | None = None
    title: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Artifact:
    """A concrete digital object whose identity does not depend on provenance."""
    artifact_id: str | None = None
    sha256: str | None = None
    size: int | None = None
    filename: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Occurrence:
    """Evidence that an Artifact occurred in a particular context."""
    occurrence_id: str | None = None
    artifact_id: str | None = None
    source_id: str | None = None
    collection_id: str | None = None
    media_id: str | None = None
    entry_id: str | None = None
    path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SoftwareRelease:
    release_id: str | None = None
    software_id: str | None = None
    version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Software:
    software_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
