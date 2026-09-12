"""Explicit linking of score references to supplied archives.

A caller supplies external casts by MCsL library ID. No path in the source is
opened, and a missing cast remains an unresolved observation.
"""

from dataclasses import dataclass
from .archive import CastMember
from .binary import DirectorError
from .lingo import Script, read_context, read_names, read_script


@dataclass(frozen=True)
class MemberLink:
    library: int
    member: int
    cast: CastMember
    script: Script | None
    script_unused: bool
    texts: tuple[tuple[int, bytes], ...]


class CastLinks:
    def __init__(self, movie, external_casts=None):
        self.members = {}
        self.unresolved_libraries = []
        supplied = dict(external_casts or {})
        libraries = movie.libraries()
        ids = {lib.id for lib in libraries}
        if not supplied.keys() <= ids:
            raise DirectorError("Supplied cast ID is absent from MCsL")
        for lib in libraries:
            if lib.path:
                if lib.id not in supplied:
                    self.unresolved_libraries.append(lib.id)
                    continue
                archive = supplied[lib.id]
                parent = 1024  # Standalone D6 casts use the root logical library.
                first, last = archive.standalone_bounds()
                if (first, last) != (lib.first_member, lib.last_member):
                    raise DirectorError(f"External cast {lib.id}: DRCF bounds differ from MCsL")
            else:
                if lib.id in supplied:
                    raise DirectorError("Cannot replace an embedded cast with an external archive")
                archive, parent = movie, lib.resource_id
            keys = archive.keys()
            tables = [k.child for k in keys if k.tag == "CAS*" and k.parent == parent]
            contexts = [k.child for k in keys if k.tag == "Lctx" and k.parent == parent]
            if len(tables) != 1 or len(contexts) > 1:
                raise DirectorError(f"Library {lib.id}: ambiguous or missing cast/context table")
            scripts = {}
            if contexts:
                context = read_context(archive, contexts[0])
                names = read_names(archive, context.names_id)
                for entry in context.entries:
                    if entry.resource_id != -1:
                        scripts[entry.index] = (
                            read_script(archive, entry.resource_id, names),
                            entry.unused,
                        )
            for member in archive.members(tables[0]):
                number = lib.first_member + member.slot
                if number > lib.last_member:
                    raise DirectorError(f"Library {lib.id}: member outside declared bounds")
                script, unused = scripts.get(member.script_id, (None, False))
                if member.script_id and script is None:
                    raise DirectorError(f"Library {lib.id} member {number}: dangling script ID")
                self.members[(lib.id, number)] = MemberLink(
                    lib.id, number, member, script, unused, archive.text(member)
                )
        self.unresolved_libraries = tuple(self.unresolved_libraries)

    def resolve(self, sprite):
        return self.members.get((sprite.cast_library, sprite.cast_member))
