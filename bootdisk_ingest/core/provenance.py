"""Source-agnostic provenance helpers."""
from .models import Artifact, Occurrence


def occurrence_for_artifact(
    artifact: Artifact,
    *,
    source_id: str | None = None,
    collection_id: str | None = None,
    media_id: str | None = None,
    entry_id: str | None = None,
    path: str | None = None,
) -> Occurrence:
    return Occurrence(
        artifact_id=artifact.artifact_id,
        source_id=source_id,
        collection_id=collection_id,
        media_id=media_id,
        entry_id=entry_id,
        path=path,
    )
