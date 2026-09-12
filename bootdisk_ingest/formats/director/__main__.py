"""Write structural observations to stdout; never execute a Director movie."""

import argparse
from collections import Counter
from dataclasses import asdict, is_dataclass
import hashlib
import json
import sys

from . import Archive, DirectorError, Score, read_context, read_names, read_script, read_labels
from .links import CastLinks


def json_value(value):
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, bytes):
        return {"hex": value.hex(), "latin1_view": value.decode("latin1")}
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def observations(archive, casts=None):
    if len(archive.ids("VWSC")) > 1 or len(archive.ids("VWLB")) > 1:
        raise DirectorError("Observation projection requires at most one score and label table")
    scripts = []
    for rid in archive.ids("Lctx"):
        context = read_context(archive, rid)
        names = read_names(archive, context.names_id)
        for entry in context.entries:
            if entry.resource_id == -1:
                continue
            script = read_script(archive, entry.resource_id, names)
            scripts.append(
                {
                    "context": rid,
                    "entry": entry,
                    "flags": script.flags,
                    "constants": script.constants,
                    "literal_calls": script.literal_calls(),
                }
            )
    labels = [label for rid in archive.ids("VWLB") for label in read_labels(archive, rid)]
    by_frame = {}
    for label in labels:
        by_frame.setdefault(label.frame, []).append(label)
    links = CastLinks(archive, casts) if archive.libraries() else None
    frames = []
    counts = {}
    for rid in archive.ids("VWSC"):
        count = 0
        for frame in Score(archive, rid).frames():
            count += 1
            if frame.number not in by_frame:
                continue
            members = []
            for sprite in frame.sprites:
                if not sprite.kind or not sprite.cast_member:
                    continue
                link = links.resolve(sprite) if links else None
                members.append(
                    {
                        "channel": sprite.channel,
                        "cast_library": sprite.cast_library,
                        "cast_member": sprite.cast_member,
                        "detail_index": sprite.detail_index,
                        "resolved": link is not None,
                        "member_resource": link.cast.resource_id if link else None,
                        "script_id": link.cast.script_id if link else None,
                        "script_unused": link.script_unused if link else None,
                        "script_resource": (
                            link.script.resource_id if link and link.script else None
                        ),
                        "literal_calls": (
                            link.script.literal_calls() if link and link.script else ()
                        ),
                        "texts": link.texts if link else (),
                    }
                )
            frames.append(
                {
                    "score_resource": rid,
                    "frame": frame.number,
                    "labels": by_frame[frame.number],
                    "members": members,
                }
            )
        counts[rid] = count
        if any(label.frame > count for label in labels):
            raise DirectorError("Label points beyond the decoded score")
    return json_value(
        {
            "schema": "director-observations-experimental-1",
            "sha256": hashlib.sha256(archive.data).hexdigest(),
            "version": archive.version,
            "resources": dict(Counter(r.tag for r in archive.resources)),
            "libraries": archive.libraries(),
            "scripts": scripts,
            "labels": labels,
            "external_casts": {
                i: hashlib.sha256(a.data).hexdigest() for i, a in (casts or {}).items()
            },
            "unresolved_libraries": links.unresolved_libraries if links else (),
            "frame_counts": counts,
            "labeled_frames": frames,
        }
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movie")
    parser.add_argument(
        "--cast",
        action="append",
        default=[],
        metavar="ID=FILE",
        help="Explicit external cast binding; original paths are never followed",
    )
    args = parser.parse_args(argv)
    try:
        casts = {}
        for spec in args.cast:
            number, path = spec.split("=", 1)
            number = int(number)
            if number in casts:
                raise DirectorError(f"Duplicate external cast ID {number}")
            casts[number] = Archive.open(path)
        archive = Archive.open(args.movie)
        if casts and not archive.libraries():
            raise DirectorError("External bindings require MCsL")
        result = observations(archive, casts)
        json.dump(result, sys.stdout, ensure_ascii=True, indent=2)
        sys.stdout.write("\n")
        return 0
    except (OSError, ValueError) as error:
        print(f"director-reader: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
