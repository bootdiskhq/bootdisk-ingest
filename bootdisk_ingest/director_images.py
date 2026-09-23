"""Extract score-bound K-CD image resources without rendering or executing them."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from .adapters.kcd.director import MenuProjection
from .core.inventory import FileInventory, FileRecord
from .formats.director import Archive, DirectorError
from .formats.director.binary import View

SCHEMA = 'bootdisk-embedded-images-1'
METHOD = 'kcd-d6-score-images-1'


def bitmap_layout(data):
    v = View(data, 'D6 bitmap metadata')
    pitch = v.u16(0)
    top, left, bottom, right = [v.i16(p) for p in (2, 4, 6, 8)]
    width, height = right-left, bottom-top
    v.require(bool(pitch & 0x8000) and v.span(23, 1)[0] == 8, 0, 'only indexed 8-bit images supported')
    pitch &= 0x3fff
    v.require(0 < width <= pitch <= 4096 and 0 < height <= 4096 and pitch*height <= 16*1024*1024,
              0, 'invalid image dimensions')
    return {'width': width, 'height': height, 'row_stride': pitch,
            'palette_library': v.i16(24), 'palette_member': v.i16(26)}


def select_images(entry, frames, links):
    """Qualified K-CD layout: unique 195x145 detail and 32x32 title-row icon."""
    def bitmaps(frame):
        for sprite in frame.sprites:
            link = links.resolve(sprite)
            if sprite.kind and link and link.cast.kind == 1:
                try:
                    layout = bitmap_layout(link.cast.data)
                except DirectorError:
                    continue
                yield sprite, link, layout
    selected, issues = [], []
    detail = frames[entry['evidence']['frame_action']['frame']-1]
    shots = [(s,l,d) for s,l,d in bitmaps(detail) if (d['width'],d['height']) == (195,145)]
    if len(shots) == 1:
        selected.append(('screenshot', detail, *shots[0], 'unique 195x145 bitmap in selected detail frame'))
    else:
        issues.append('missing_or_ambiguous_detail_image')
    if entry['evidence']['selection']['method'] == 'clickable menu text':
        overview = frames[entry['evidence']['selection']['frame']-1]
        title = next(s for s in overview.sprites if s.channel == entry['evidence']['selection']['channel'])
        t = View(title.raw, 'title sprite')
        top, height = t.i16(12), t.u16(16)
        icons = [(s,l,d) for s,l,d in bitmaps(overview) if (d['width'],d['height']) == (32,32)
                 and top <= View(s.raw,'icon sprite').i16(12) < top+height]
        if len(icons) == 1:
            selected.append(('icon', overview, *icons[0], 'unique 32x32 bitmap in clickable title row'))
        else:
            issues.append('missing_or_ambiguous_menu_icon')
    else:
        issues.append('no_qualified_menu_icon_layout')
    return selected, issues


def extract(manifest_path, source_root, output):
    raw = Path(manifest_path).read_bytes(); manifest = json.loads(raw)
    if manifest.get('schema_version') != 'kcd-director-experimental-1':
        raise DirectorError('requires Director ingest manifest')
    ref = 'sha256:' + hashlib.sha256(raw).hexdigest()
    root = Path(source_root).resolve(); archives, sources = {}, {}
    for source in manifest['source']['files']:
        relative = source['path']; path = (root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise DirectorError('source escapes media root or is missing')
        archive = Archive.open(path)
        if len(archive.data) != source['size'] or hashlib.sha256(archive.data).hexdigest() != source['sha256']:
            raise DirectorError('Director source changed since ingest')
        archives[relative] = archive
        sources[relative] = {k: source[k] for k in ('path','size','sha256')}
    movie = archives['K-CN.dxr']
    bindings = {s['library']: s['source_path'] for s in manifest['source']['library_sources'] if s['source_path']}
    casts = {lib.id: archives[bindings[lib.id]] for lib in movie.libraries() if lib.path and lib.id in bindings}
    inventory = FileInventory.from_records(FileRecord(**r) for r in manifest['file_inventory'])
    projection = MenuProjection(movie, casts, inventory); actual = projection.entries()
    if len(actual) != len(manifest['entries']):
        raise DirectorError('source menu differs from manifest')
    for old, new in zip(manifest['entries'], actual):
        if old['source_id'] != new['source_id'] or any(old['evidence'][k] != new['evidence'][k] for k in ('selection','frame_action')):
            raise DirectorError('source entry/frame binding mismatch')
    blobs, assets, outcomes = {}, [], []
    def resource(library, rid, tag):
        path = bindings[library]; archive = archives[path]; r = archive.resource(rid, tag)
        data = archive.payload(rid, tag); digest = hashlib.sha256(data).hexdigest(); blobs[digest] = data
        return {'sha256':digest,'size':len(data),'object_path':'resources/'+digest,
                'container':sources[path], 'offset':r.offset+8,'resource_id':rid,'tag':tag}
    def child(link, tag):
        archive = archives[bindings[link.library]]
        matches = [k.child for k in archive.keys() if k.parent == link.cast.resource_id and k.tag == tag]
        if len(matches) != 1: raise DirectorError('missing/ambiguous image resource')
        return resource(link.library,matches[0],tag)
    for entry in actual:
        selected, issues = select_images(entry, projection.frames, projection.links)
        for kind, frame, sprite, link, layout, rule in selected:
            number = layout['palette_member']; lib = layout['palette_library']
            # K-CD zero-library palettes resolve only to a unique actual palette
            # among explicitly bound sources; never substitute a default palette.
            palettes = [p for (l,n),p in projection.links.members.items() if n == number and p.cast.kind == 4
                        and (lib == 0 or l == (link.library if lib == -1 else lib))]
            if len(palettes) != 1: raise DirectorError('missing/ambiguous palette binding')
            palette = child(palettes[0], 'CLUT')
            if palette['size'] != 1536: raise DirectorError('requires complete 256-color palette')
            assets.append({'entry_source_id':entry['source_id'],'entry_title':entry['normalized']['title'],
                'kind':kind,'source_ref':{'manifest':ref,'entry':entry['source_id']},
                'selection':{**projection.location(frame,sprite,link),'rule':rule,'sprite_hex':sprite.raw.hex()},
                'pixels':child(link,'BITD'),'palette':palette,'metadata':resource(link.library,link.cast.resource_id,'CASt'),
                'raster':{'width':layout['width'],'height':layout['height'],'row_stride':layout['row_stride'],
                          'encoding':'indexed8-rle257-or-raw','palette_encoding':'rgb16be-high-byte'},
                'palette_binding':{'declared_library':lib,'member':number,'resolved_library':palettes[0].library}})
        outcomes.append({'entry':entry['source_id'],'issues':issues})
    report = {'schema':SCHEMA,'method':METHOD,'manifest':ref,'sources':list(sources.values()),'assets':assets,'outcomes':outcomes}
    output = Path(output).absolute()
    if output.resolve().is_relative_to(root):
        raise DirectorError('output must be outside source media')
    if output.exists() or output.is_symlink(): raise DirectorError('output must be a new directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.images-',dir=output.parent))
    try:
        (stage/'resources').mkdir()
        (stage/'containers').mkdir()
        for path, archive in archives.items():
            (stage/'containers'/sources[path]['sha256']).write_bytes(archive.data)
        for digest,data in blobs.items(): (stage/'resources'/digest).write_bytes(data)
        (stage/'images.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        os.rename(stage,output)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=extract(a.manifest,a.source,a.output)
    print(f"embedded assets: {len(r['assets'])}; entries: {len(r['outcomes'])}")

if __name__=='__main__':main()
