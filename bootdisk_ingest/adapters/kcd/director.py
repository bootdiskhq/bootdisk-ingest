"""K-CD's pre-DTX menu conventions projected from structural D6 evidence.

This is deliberately not a Lingo VM. Selection means a score-backed menu
candidate under the documented K-CD profile, never proven runtime reachability.
"""

import base64
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

from bootdisk_ingest.config import PARSER_VERSION
from bootdisk_ingest.core.identity import build_content_identity
from bootdisk_ingest.core.inventory import FileInventory, FileRecord
from bootdisk_ingest.formats.director import Archive, DirectorError, Score, read_labels
from bootdisk_ingest.formats.director.links import CastLinks
from bootdisk_ingest.validation import build_validation

SOURCE_FORMAT = "kcd-director-d6-v1"


def raw_value(value):
    if isinstance(value, bytes):
        return {
            "base64": base64.b64encode(value).decode("ascii"),
            "cp1252_view": value.decode("cp1252", errors="replace"),
        }
    return value


def relative_target(value):
    """Accept only a literal disc-relative path, not a command line or host path."""
    if not isinstance(value, bytes):
        raise ValueError("Target is not a literal byte string")
    path = value.decode("cp1252").replace("\\", "/")
    if (
        not path
        or path.startswith("/")
        or any(c in path for c in ':\x00\r\n"')
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ValueError("Target is not an unambiguous disc-relative path")
    return path


def launch_path(call):
    """Interpret only qualified Buddy API signatures; keep their full arguments."""
    args = call.arguments
    if call.name.lower() == b"barunprogram" and len(args) == 3:
        return relative_target(args[0])
    if (
        call.name.lower() == b"bashell"
        and len(args) == 5
        and isinstance(args[0], bytes)
        and args[0].lower() == b"open"
        and args[2] == b""
        and isinstance(args[3], bytes)
    ):
        target = relative_target(args[1])
        if args[3]:
            target = relative_target(args[3]) + "/" + target
        return target
    raise ValueError("Unqualified launch signature or nonempty command arguments")


def calls(link, names=None, handler=None):
    if not link or not link.script or link.script_unused:
        return ()
    return tuple(
        c
        for c in link.script.literal_calls()
        if (names is None or c.name.lower() in names)
        and (handler is None or c.handler.lower() == handler)
    )


def go_targets(link, handler=None):
    return [
        c.arguments[0]
        for c in calls(link, {b"go"}, handler)
        if len(c.arguments) == 1 and isinstance(c.arguments[0], bytes)
    ]


class MenuProjection:
    def __init__(self, movie, casts, inventory):
        if len(movie.ids("VWSC")) != 1 or len(movie.ids("VWLB")) != 1:
            raise DirectorError("K-CD profile requires one score and one label table")
        self.links = CastLinks(movie, casts)
        self.inventory = inventory
        self.score_id = movie.ids("VWSC")[0]
        self.frames = tuple(Score(movie, self.score_id).frames())
        self.labels = {}
        self.frame_labels = {}
        self.ambiguous_labels = set()
        self.label_frames = {}
        for label in read_labels(movie, movie.ids("VWLB")[0]):
            self.label_frames.setdefault(label.name, []).append(label.frame)
            if label.name in self.labels:
                # D6 labels may legitimately repeat, but selecting one would be a guess.
                if self.labels[label.name] != label.frame:
                    self.ambiguous_labels.add(label.name)
            if not 1 <= label.frame <= len(self.frames):
                raise DirectorError("K-CD label outside score")
            self.labels[label.name] = label.frame
            self.frame_labels.setdefault(label.frame, []).append(label.name)
        self.selected_scripts = set()
        self.navigation = []

    def frame(self, label):
        if label in self.ambiguous_labels:
            raise DirectorError(f"Ambiguous K-CD label: {label!r}")
        if label not in self.labels:
            raise DirectorError(f"Missing K-CD profile label: {label!r}")
        return self.frames[self.labels[label] - 1]

    @staticmethod
    def action_key(frame):
        return (
            int.from_bytes(frame.main_channels[:2], "big"),
            int.from_bytes(frame.main_channels[2:4], "big"),
        )

    def action(self, frame):
        return self.links.members.get(self.action_key(frame))

    def sprites(self, frame):
        return ((s, self.links.resolve(s)) for s in frame.sprites if s.kind and s.cast_member)

    def location(self, frame, sprite, link):
        return {
            "score_resource": self.score_id,
            "frame": frame.number,
            "labels": [raw_value(x) for x in self.frame_labels.get(frame.number, ())],
            "channel": sprite.channel if sprite else None,
            "library": link.library,
            "member": link.member,
            "member_resource": link.cast.resource_id,
            "script_resource": link.script.resource_id if link.script else None,
        }

    def page_chain(self):
        """Follow the qualified KxD6 next-page state, not stored menu counts."""
        page, seen = 1, set()
        while page not in seen:
            seen.add(page)
            label = f"KDisk{page}Mere".encode()
            frame = self.frame(label)
            yield page, frame
            next_label = f"K{page}D6".encode()
            if next_label not in go_targets(self.action(frame), b"enterframe"):
                raise DirectorError("Unqualified K-CD next-page selector")
            nav_candidates = [
                self.frames[n - 1]
                for n in self.label_frames.get(next_label, ())
                if self.action_key(self.frames[n - 1]) == self.action_key(frame)
            ]
            if len(nav_candidates) != 1:
                raise DirectorError("Ambiguous next-page state within menu action")
            nav_frame = nav_candidates[0]
            destinations = set()
            evidence = []
            for sprite, link in self.sprites(nav_frame):
                for target in go_targets(link, b"mouseup"):
                    match = re.fullmatch(rb"KDisk([1-9][0-9]*)Mere", target)
                    if match:
                        destinations.add(int(match[1]))
                        evidence.append(
                            {
                                **self.location(nav_frame, sprite, link),
                                "destination": raw_value(target),
                            }
                        )
            if len(destinations) != 1:
                raise DirectorError("Unqualified or ambiguous K-CD next-page button")
            self.navigation.append(
                {
                    "page": page,
                    "selector_frame": frame.number,
                    "next_state": raw_value(next_label),
                    "all_label_frames": self.label_frames[next_label],
                    "selection": "same frame action as menu; not runtime label resolution",
                    "buttons": evidence,
                }
            )
            page = destinations.pop()

    def game_groups(self):
        """Follow game-frame scripts and their score-linked buttons from Spil2."""
        pending, seen, groups = [b"Spil2"], set(), {}
        while pending:
            label = pending.pop(0)
            if label in seen:
                continue
            seen.add(label)
            frame = self.frame(label)
            action = self.action(frame)
            number = int(label[4:])
            group = 1 if number < 10 else number // 10
            idle = b"Spil2" if group == 1 else f"Spil{group}1".encode()
            if not action or idle not in go_targets(action, b"enterframe"):
                raise DirectorError("Unqualified K-CD game frame action")
            key = self.action_key(frame)
            groups.setdefault(key, (frame, group))
            targets = go_targets(action, b"enterframe")
            for sprite, link in self.sprites(frame):
                targets.extend(go_targets(link, b"mouseup"))
            for target in targets:
                if re.fullmatch(rb"Spil[0-9]+", target) and target not in seen:
                    pending.append(target)
        return groups

    def texts(self, frames):
        out, seen = [], set()
        for frame in frames:
            for sprite, link in self.sprites(frame):
                if not link:
                    continue
                for rid, value in link.texts:
                    key = link.library, link.member, rid
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(
                        {
                            **self.location(frame, sprite, link),
                            "text_resource": rid,
                            "text": raw_value(value),
                        }
                    )
        return out

    def entry(self, source_id, title, selection, anchor, chicken, category):
        action = self.action(anchor)
        if not action or not action.script or action.script_unused:
            raise DirectorError(f"Unresolved entry frame action: {source_id}")
        key = self.action_key(anchor)
        frame_numbers = {anchor.number}
        for target in go_targets(action, b"enterframe"):
            frame_numbers.update(
                n
                for n in self.label_frames.get(target, ())
                if self.action_key(self.frames[n - 1]) == key
            )
        frames = [self.frames[n - 1] for n in sorted(frame_numbers)]
        warning_frame = self.frame(chicken)
        branches = {"direct": [], "warning_continue": []}
        other_controls = []
        unresolved = []
        for branch, branch_frames in (("direct", frames), ("warning_continue", [warning_frame])):
            seen = set()
            for frame in branch_frames:
                for sprite, link in self.sprites(frame):
                    if not link:
                        item = {
                            "branch": branch,
                            "frame": frame.number,
                            "channel": sprite.channel,
                            "library": sprite.cast_library,
                            "member": sprite.cast_member,
                        }
                        if item not in unresolved:
                            unresolved.append(item)
                        continue
                    for call in calls(link, {b"barunprogram", b"bashell"}, b"mouseup"):
                        primary = (
                            chicken in go_targets(link, b"mouseup")
                            if branch == "direct"
                            else sprite.channel == 91
                        )
                        ident = link.library, link.member, call.offset, primary
                        if ident in seen:
                            continue
                        seen.add(ident)
                        self.selected_scripts.add((link.library, link.member))
                        observation = {
                            **self.location(frame, sprite, link),
                            "handler": raw_value(call.handler),
                            "offset": call.offset,
                            "function": raw_value(call.name),
                            "arguments": [raw_value(a) for a in call.arguments],
                        }
                        try:
                            path = launch_path(call)
                            record, mismatch = self.inventory.find(path)
                            observation["file"] = {"path": path, "exists": record is not None}
                            if record:
                                observation["file"].update(
                                    size=record.size,
                                    sha256=record.sha256,
                                    resolved_path=record.path,
                                    path_case_mismatch=mismatch,
                                )
                        except ValueError as error:
                            observation["unresolved_reason"] = str(error)
                        observation["page_context"] = branch
                        (branches[branch] if primary else other_controls).append(observation)
        issues = []
        for branch, values in branches.items():
            if not values:
                issues.append(f"unresolved_{branch}_launch")
            if any("unresolved_reason" in v for v in values):
                issues.append(f"unresolved_{branch}_target")
        paths = {
            (
                v["file"].get("resolved_path")
                if v["file"]["exists"]
                else v["file"]["path"].casefold()
            )
            for vs in branches.values()
            for v in vs
            if "file" in v
        }
        if len(paths) > 1:
            issues.append("conflicting_launch_targets")
        referenced = {
            f"{branch}_{i + 1}": v["file"]
            for branch, vs in branches.items()
            for i, v in enumerate(vs)
            if "file" in v
        }
        records = {
            v["resolved_path"]: self.inventory.by_path[v["resolved_path"]]
            for v in referenced.values()
            if v["exists"]
        }
        if any(not v["exists"] for v in referenced.values()):
            issues.append("missing_launch_file")
        texts = self.texts(frames)
        overview = anchor if category == "games" else self.frame(source_id.encode())
        overview_texts = self.texts([overview])
        candidates = [
            t
            for t in overview_texts
            if (
                t["channel"] == 14
                if category == "games"
                else len(base64.b64decode(t["text"]["base64"]).strip()) >= 80
            )
        ]
        description = candidates[0] if len(candidates) == 1 else None
        # The projection keeps all score-backed texts; no global name-based join.
        return {
            "source_id": source_id,
            "raw": {},
            "normalized": {
                "title": " ".join(title.split()),
                "description": (
                    description["text"]["cp1252_view"].strip() if description else None
                ),
                "installer": None,
                "run": None,
                "categories": [category],
                "requirements": {"cpu": {"interpretation": None}},
            },
            "interpretations": {
                "selection": "score_backed_menu_candidate_not_runtime_proof",
                "warning_association": "K-CD ordinal Chicken-label and continue channel 91 conventions",
                "direct_association": "same mouseUp script contains go to the associated Chicken label",
                "description_selection": (
                    "game channel 14"
                    if category == "games"
                    else "unique overview text of at least 80 bytes; heuristic"
                ),
                "title_encoding": "CP1252 display view; exact bytes retained in evidence",
                "content_identity_scope": "resolved literal launch files only, not software package",
            },
            "evidence": {
                "selection": selection,
                "frame_action": self.location(anchor, None, action),
                "texts": texts,
                "overview_texts": overview_texts,
                "description_source": description,
                "warning_label": raw_value(chicken),
                "launches": branches,
                "other_launch_controls": other_controls,
                "unresolved_sprite_references": unresolved,
            },
            "issues": issues,
            "files": {
                "referenced": referenced,
                "discovered": {},
                "inventory_refs": sorted(records),
            },
            "content_identity": build_content_identity(records.values()),
        }

    def entries(self):
        out = []
        for key, (anchor, number) in self.game_groups().items():
            title_sprite = next((s for s in anchor.sprites if s.channel == 10 and s.kind), None)
            link = self.links.resolve(title_sprite) if title_sprite else None
            if not link or len(link.texts) != 1:
                raise DirectorError("Unqualified K-CD game title channel")
            value = link.texts[0][1]
            selection = {
                **self.location(anchor, title_sprite, link),
                "title": raw_value(value),
                "method": "Spil2 game navigation and title channel 10",
            }
            out.append(
                self.entry(
                    f"Spil{number}",
                    value.decode("cp1252", errors="replace").strip(),
                    selection,
                    anchor,
                    f"S{number}Chicken".encode(),
                    "games",
                )
            )
        for page, frame in self.page_chain():
            seen = set()
            for sprite, link in self.sprites(frame):
                if not link or not link.texts:
                    continue
                for target in go_targets(link, b"mouseup"):
                    match = re.fullmatch(rb"K([1-9][0-9]*)D([1-5])[0-9]+", target)
                    if not match or int(match[1]) != page:
                        continue
                    slot = int(match[2])
                    if slot in seen:
                        raise DirectorError("Ambiguous K-CD menu entry")
                    seen.add(slot)
                    if len(link.texts) != 1:
                        raise DirectorError("Ambiguous K-CD menu title")
                    value = link.texts[0][1]
                    if not value.strip():
                        continue
                    selection = {
                        **self.location(frame, sprite, link),
                        "title": raw_value(value),
                        "destination": raw_value(target),
                        "method": "clickable menu text",
                    }
                    out.append(
                        self.entry(
                            f"K{page}D{slot}",
                            value.decode("cp1252", errors="replace").strip(),
                            selection,
                            self.frame(target),
                            f"K{(page - 1) * 5 + slot}Chicken".encode(),
                            "programs",
                        )
                    )
            if not seen:
                raise DirectorError("K-CD menu page has no qualified clickable titles")
        return out


def parse_director_disc(disc_root, disc_inventory, *, generated_at=None):
    inventory = FileInventory.from_records(FileRecord(**r) for r in disc_inventory["files"])
    root = Path(disc_root)
    sources = []

    def open_source(name):
        record, mismatch = inventory.find(name)
        if not record:
            raise DirectorError(f"Required K-CD Director source missing: {name}")
        archive = Archive.open(root / record.path)
        if (
            len(archive.data) != record.size
            or hashlib.sha256(archive.data).hexdigest() != record.sha256
        ):
            raise DirectorError(f"{record.path} changed after inventory; ingest a stable source")
        sources.append({**asdict(record), "requested_path": name, "path_case_mismatch": mismatch})
        return archive

    movie = open_source("K-CN.dxr")
    # Bind only the qualified Constant library. Never open authoring-drive paths.
    libraries = [
        lib
        for lib in movie.libraries()
        if lib.path.replace(b"\\", b"/").split(b"/")[-1].lower() == b"constant.cxt"
    ]
    if len(libraries) != 1:
        raise DirectorError("K-CD profile requires one declared Constant.cxt library")
    casts = {libraries[0].id: open_source("Constant.cxt")}
    cast_paths = {libraries[0].id: sources[-1]["path"]}
    for lib in movie.libraries():
        basename = lib.path.replace(b"\\", b"/").split(b"/")[-1].lower()
        if basename in (b"norsk.cst", b"norsk.cxt") and inventory.find("Norsk.cxt")[0]:
            casts[lib.id] = open_source("Norsk.cxt")
            cast_paths[lib.id] = sources[-1]["path"]
    projection = MenuProjection(movie, casts, inventory)
    entries = projection.entries()
    detached = []
    for key, link in sorted(projection.links.members.items()):
        launch_calls = calls(link, {b"barunprogram", b"bashell"})
        if launch_calls and key not in projection.selected_scripts:
            detached.append(
                {
                    "library": key[0],
                    "member": key[1],
                    "script_resource": link.script.resource_id,
                    "calls": [
                        {
                            "handler": raw_value(c.handler),
                            "offset": c.offset,
                            "function": raw_value(c.name),
                            "arguments": [raw_value(a) for a in c.arguments],
                        }
                        for c in launch_calls
                    ],
                }
            )
    return {
        "schema_version": "kcd-director-experimental-1",
        "generator": {
            "name": "bootdisk-ingest",
            "version": PARSER_VERSION,
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        },
        "source": {
            "format": SOURCE_FORMAT,
            "files": sources,
            "library_sources": [
                {
                    "library": lib.id,
                    "name": raw_value(lib.name),
                    "declared_path": raw_value(lib.path),
                    "source_path": (
                        cast_paths[lib.id]
                        if lib.id in casts
                        else sources[0]["path"] if not lib.path else None
                    ),
                }
                for lib in movie.libraries()
            ],
            "profile": "K-CD 1/2000 and 4/2000; D6 0x04c7",
            "navigation": projection.navigation,
            "unresolved_libraries": list(projection.links.unresolved_libraries),
            "unselected_launch_scripts": detached,
            "limitations": [
                "Static menu candidates, not runtime reachability or execution",
                "Movie, Constant.cxt and available declared Norsk.cxt are linked",
                "Scope: games and KDisk program menus, not every disc section",
                "Computed launch arguments and sprite behaviors are not evaluated",
                "Chicken labels and game title channel are K-CD conventions",
                "Unselected scripts may be reusable, stale, or outside this profile",
            ],
        },
        "disc": {"raw": {}, "content_identity": build_content_identity(disc_inventory["files"])},
        "entries": entries,
    }


def validate_director(entries):
    result = build_validation(entries)
    issues = [
        {"source_id": entry["source_id"], "issues": entry["issues"]}
        for entry in entries
        if entry["issues"]
    ]
    result["entry_issues"] = issues
    result["valid"] = result["valid"] and not issues and bool(entries)
    result["scope"] = "Static launch-reference consistency, not runtime or catalog completeness"
    if issues:
        result["warnings"].append(
            f"{len(issues)} entries have conflicting or unresolved launch evidence"
        )
    return result
