"""Read score-bound workshop entries as a separate additive manifest.

No source program is run. Existing manifests and curator decisions are not
rewritten. The shelf/action/intro conventions are explicit K-CD profile rules.
"""
import argparse
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import struct

from .adapters.kcd.director import raw_value, relative_target
from .core.identity import build_content_identity
from .core.inventory import FileInventory, FileRecord
from .formats.director import DirectorError, Score, read_labels
from .formats.director.afterburner import SourceArchive
from .formats.director.links import CastLinks
from .output import write_manifest


def properties(raw):
    """Split flat property lists without interpreting source commands."""
    text = raw.rstrip(b'\0').decode('cp1252')
    if not text.startswith('[') or not text.endswith(']'):
        raise DirectorError('Unsupported behavior initializer')
    parts = []; start = 1; quoted = False
    for i, c in enumerate(text[1:-1], 1):
        if c == '"': quoted = not quoted
        elif c == ',' and not quoted:
            parts.append(text[start:i]); start = i+1
    if quoted:
        raise DirectorError('Unterminated initializer string')
    parts.append(text[start:-1]); result = {}
    for part in parts:
        match = re.fullmatch(r'\s*#([A-Za-z][A-Za-z0-9_]*):\s*(.*?)\s*', part, re.S)
        if not match or match[1].lower() in result:
            raise DirectorError('Ambiguous behavior initializer')
        result[match[1].lower()] = match[2]
    return result


def literal_string(expression):
    # Only string literals joined by & and the built-in quote constant.
    token = r'(?:"[^"\x00]*"|QUOTE)'
    if not re.fullmatch(token + r'(?:\s*&\s*' + token + ')*', expression, re.I):
        raise DirectorError('Computed behavior command is not qualified')
    return ''.join('"' if s.upper() == 'QUOTE' else s[1:-1]
                   for s in re.findall(token, expression, re.I))


def consumes_property(script, name):
    if script is None:
        return False
    for handler in script.handlers:
        if handler.name.lower() != b'mouseup':
            continue
        ins = handler.instructions
        for a,b,c in zip(ins,ins[1:],ins[2:]):
            if (a.opcode == 0x61 and a.operand < len(script.names)
                and script.names[a.operand].lower() == name.encode()
                and b.opcode == 0x42 and b.operand == 1 and c.opcode == 0x57
                and c.operand < len(script.names) and script.names[c.operand].lower() == b'do'):
                return True
    return False


class Workshop:
    def __init__(self, movie, casts):
        self.movie = movie
        self.links = CastLinks(movie, casts)
        if len(movie.ids('VWSC')) != 1 or len(movie.ids('VWLB')) != 1:
            raise DirectorError('Workshop requires one score and labels')
        self.score = Score(movie, movie.ids('VWSC')[0]); self.frames = tuple(self.score.frames())
        self.labels = {}
        for label in read_labels(movie, movie.ids('VWLB')[0]):
            self.labels.setdefault(label.name, []).append(label.frame)

    def frame(self, target):
        values = self.labels.get(target, [])
        if not values:
            values = [f for k, fs in self.labels.items() if k.lower() == target.lower() for f in fs]
        if len(values) != 1 or not 1 <= values[0] <= len(self.frames):
            raise DirectorError('Missing/ambiguous workshop destination ' + repr(target))
        return self.frames[values[0]-1]

    def location(self, frame, sprite, link):
        return {'frame': frame.number, 'channel': sprite.channel, 'score_resource': self.score.resource_id,
                'library': link.library, 'member': link.member, 'member_resource': link.cast.resource_id}

    def text(self, frame, channel):
        sprite = frame.sprites[channel-1]
        link = self.links.resolve(sprite) if sprite.kind else None
        if not link or len(link.texts) != 1:
            return None
        rid, value = link.texts[0]
        return {**self.location(frame, sprite, link), 'text_resource': rid, 'text': raw_value(value)}

    def commands(self, frame, sprite, field):
        if not sprite.kind or not sprite.detail_index:
            return []
        header = self.score.detail(sprite.detail_index)
        if len(header) < 44:
            raise DirectorError('Short sprite detail')
        start, end = struct.unpack('>II', header[:8])
        if not start <= frame.number <= end:
            raise DirectorError('Sprite detail outside frame span')
        raw = self.score.detail(sprite.detail_index+1)
        if len(raw)%8 or len(raw)>8*128:
            raise DirectorError('Unsupported sprite behavior list')
        out=[]
        for i in range(0,len(raw),8):
            lib, member, index = struct.unpack('>HHI', raw[i:i+8])
            link = self.links.members.get((lib,member))
            if not index or not link or link.script_unused:
                continue
            props_raw = self.score.detail(index)
            props = properties(props_raw)
            if field not in props or not consumes_property(link.script, field):
                continue
            out.append({'command': literal_string(props[field]), 'initializer': raw_value(props_raw),
                        'initializer_index': index, 'behavior_library': lib, 'behavior_member': member,
                        'script_resource': link.script.resource_id, 'frame': frame.number,
                        'channel': sprite.channel, 'detail_index': sprite.detail_index})
        return out

    def entries(self, inventory, root):
        out=[]; seen=set(); coverage=[]
        shelves=sorted(k for k in self.labels if re.fullmatch(rb'Hylde[1-9][0-9]*',k))
        if not shelves or b'V1' not in self.labels:
            raise DirectorError('No qualified workshop shelf labels')
        for shelf in shelves:
            frame=self.frame(shelf); selected=0
            for sprite in frame.sprites:
                commands=self.commands(frame,sprite,'correctcommand')
                if not commands: continue
                if len(commands)!=1:
                    raise DirectorError('Ambiguous shelf navigation')
                command=commands[0]
                match=re.fullmatch(r'go to frame "([^"\r\n]+)"',command['command'],re.I)
                if not match:
                    raise DirectorError('Unqualified shelf destination')
                label=match[1].encode('cp1252')
                title=self.text(frame,sprite.channel+2)
                if not title or not title['text']['cp1252_view'].strip():
                    raise DirectorError('Missing shelf title')
                if label in seen:
                    raise DirectorError('Duplicate workshop destination')
                seen.add(label);selected+=1
                anchor=self.frame(label)
                if anchor.number >= len(self.frames): raise DirectorError('Missing workshop introduction')
                intro=self.frames[anchor.number]
                heading=self.text(intro,39)
                intro_texts=[self.text(intro,s.channel) for s in intro.sprites if s.kind]
                intro_texts=[t for t in intro_texts if t is not None]
                candidates=[t for t in intro_texts if 1 <= t['channel'] <= 114
                            and t['channel'] not in (109,110,111,112)
                            and len(t['text']['cp1252_view'].strip()) >= 80]
                candidates.sort(key=lambda t:len(t['text']['cp1252_view']),reverse=True)
                desc=candidates[0] if candidates and (len(candidates)==1 or len(candidates[0]['text']['cp1252_view'])>len(candidates[1]['text']['cp1252_view'])) else None
                # Preserve shelf label as the title; channel 39 is corroborating evidence.
                title_value=title['text']['cp1252_view'].split('\r',1)[0].strip()
                launches=[]
                for s in intro.sprites:
                    for launch in self.commands(intro,s,'runcommand'):
                        m=re.fullmatch(r'barunprogram\("([^"\r\n]+)",\s*"Normal",\s*false\)',launch['command'],re.I)
                        if not m:
                            m=re.fullmatch(r'open "launcher (Tools[^"\r\n]+)"',launch['command'],re.I)
                        if m:
                            value=m[1]
                        else:
                            m=re.fullmatch(r'baShell\("open",\s*"([^"\r\n]+)",\s*"",\s*"([^"\r\n]+)",\s*"normal"\)',launch['command'],re.I)
                            if not m: continue
                            value=m[2]+'\\'+m[1]
                        path=relative_target(value.encode('cp1252'))
                        if not path.casefold().startswith('tools/'):
                            continue
                        record,mismatch=inventory.find(path)
                        file={'path':path,'exists':record is not None}
                        if record:
                            actual=(root/record.path).resolve()
                            if not actual.is_relative_to(root):raise DirectorError('Launch escapes source')
                            raw=actual.read_bytes()
                            if len(raw)!=record.size or hashlib.sha256(raw).hexdigest()!=record.sha256:
                                raise DirectorError('Launch changed since inventory')
                            file.update(size=record.size,sha256=record.sha256,resolved_path=record.path,path_case_mismatch=mismatch)
                        launches.append({**launch,'file':file})
                refs={f'launch_{i+1}':v['file'] for i,v in enumerate(launches)}
                records={v['resolved_path']:inventory.by_path[v['resolved_path']] for v in refs.values() if v['exists']}
                issues=[]
                if not launches:issues.append('unresolved_workshop_launch')
                if any(not v['exists'] for v in refs.values()):issues.append('missing_launch_file')
                if len({v.get('resolved_path',v['path']) for v in refs.values()})>1:issues.append('conflicting_launch_targets')
                if desc is None:issues.append('description_not_selected')
                out.append({'source_id':'Tool'+label.hex(),'raw':{},
                    'normalized':{'title':title_value,'description':desc['text']['cp1252_view'] if desc else None,
                                  'installer':None,'run':None,'categories':['tools'], 'requirements':{'cpu':{'interpretation':None}}},
                    'interpretations':{'selection':'score_bound_workshop_shelf_not_runtime_proof',
                        'title_encoding':'CP1252 display view; exact bytes retained in evidence',
                        'description_selection':'longest intro body text (channels 1-114 excluding shared installer controls); heuristic, all intro texts retained',
                        'content_identity_scope':'resolved literal launch files only, not software package'},
                    'evidence':{'selection':{**title,'method':'workshop shelf behavior','shelf':raw_value(shelf),'navigation':command},
                        'destination':raw_value(label),'frame_action':{'frame':intro.number},'heading':heading,
                        'description_source':desc,'intro_texts':intro_texts,'launches':launches},
                    'issues':issues,'files':{'referenced':refs,'discovered':{},'inventory_refs':sorted(records)},
                    'content_identity':build_content_identity(records.values())})
            coverage.append({'label':raw_value(shelf),'frame':frame.number,'selected':selected})
        return out,coverage


def observe(source_root, inventory_manifest, *, context=None):
    root=Path(source_root).resolve(); raw=Path(inventory_manifest).read_bytes(); previous=json.loads(raw)
    rows=previous['file_inventory']; inventory=FileInventory.from_records(FileRecord(**r) for r in rows)
    sources=[];archives={}
    def open_source(name):
        rec,mismatch=inventory.find(name)
        if rec is None:raise DirectorError('Missing workshop source '+name)
        path=(root/rec.path).resolve()
        if not path.is_relative_to(root):raise DirectorError('Source escapes root')
        data=path.read_bytes()
        if len(data)!=rec.size or hashlib.sha256(data).hexdigest()!=rec.sha256:raise DirectorError('Source changed since inventory')
        a=SourceArchive(data);archives[rec.path]=a
        sources.append({**asdict(rec),'missing_terminal_alignment_byte':a.missing_alignment_byte})
        return a,rec.path
    movie,name=open_source('K-CN.dcr' if inventory.find('K-CN.dcr')[0] else 'K-CN.dxr')
    casts={};bindings=[]
    qualified={'constant.cxt':['Constant.cxt'],'norsk.cst':['Norsk.cxt'],'norsk.cxt':['Norsk.cxt'],
               'v_const.cst':['V_Const.cxt'],'v_norsk.cst':['V_Norsk.cxt','V_Norsk.cct'],'vconst.cst':['VConst.cct']}
    for lib in movie.libraries():
        source_path=name if not lib.path else None
        if lib.path:
            basename=lib.path.replace(b'\\',b'/').split(b'/')[-1].decode('cp1252').lower()
            names=[n for n in qualified.get(basename,[]) if inventory.find(n)[0]]
            if len(names)!=1:raise DirectorError('Unknown or ambiguous workshop library '+basename)
            casts[lib.id],source_path=open_source(names[0])
        bindings.append({'library':lib.id,'source_path':source_path,'declared_path':raw_value(lib.path)})
    workshop=Workshop(movie,casts);entries,coverage=workshop.entries(inventory,root)
    if context is not None:
        context.update(workshop=workshop,archives=archives,bindings=bindings,sources=sources)
    return {'schema_version':'kcd-director-experimental-1','generator':{'name':'bootdisk-ingest','version':'legacy-tools-1'},
        'source':{'format':'kcd-director-d6-v1','profile':'additive workshop shelves; legacy-tools-1',
            'files':sources,'library_sources':bindings,'inventory_manifest':'sha256:'+hashlib.sha256(raw).hexdigest(),
            'navigation':coverage,'limitations':['Static shelf/action observations, not execution or whole-disc completeness']},
        'disc':previous['disc'],'file_inventory':rows,'entries':entries,
        'validation':{'valid':all(not e['issues'] for e in entries),'entry_issues':[{'source_id':e['source_id'],'issues':e['issues']} for e in entries if e['issues']]}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source_root',type=Path);p.add_argument('inventory_manifest',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--images',type=Path,help='New directory for preserved shelf artwork')
    args=p.parse_args()
    if args.output.resolve().is_relative_to(args.source_root.resolve()):p.error('Output must be outside source')
    for target in (args.output,args.images):
        if target is not None and (target.exists() or target.is_symlink() or target.resolve().is_relative_to(args.source_root.resolve())):
            p.error('Outputs must be new and outside source media')
    context={}
    result=observe(args.source_root,args.inventory_manifest,context=context);write_manifest(result,args.output,overwrite=False)
    if args.images:
        if args.images.resolve().is_relative_to(args.source_root.resolve()):p.error('Images must be outside source')
        from .workshop_images import extract
        images=extract(args.output,context,args.images)
        print(f"Shelf artworks: {len(images['assets'])}")
    print(f"Workshop entries: {len(result['entries'])}; entries with issues: {len(result['validation']['entry_issues'])}")

if __name__=='__main__':main()
