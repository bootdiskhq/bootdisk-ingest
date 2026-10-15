"""Bounded Norwegian archive, classic and guide sections on four 2000 K-CDs.

Reads score-bound text and literal calls only. Never executes historical code.
"""
import argparse, hashlib
from pathlib import Path
from .legacy_tools import observe as observe_workshop
from .adapters.kcd.director import calls, go_targets, launch_path, relative_target, raw_value
from .core.identity import build_content_identity
from .core.inventory import FileRecord
from .output import write_manifest

MEDIA = {'kcd-1-2000': 'Wolfenstein 3D', 'kcd-4-2000': 'Doom',
         'kcd-9-2000': 'Crosses and Noughts', 'kcd-13-2000': 'MarbleJongg 2000'}


def resolve_file(path, inventory, root):
    # Do not repair drive letters, control characters or guessed basenames.
    safe = bool(path) and not any(ord(c)<32 for c in path) and ':' not in path
    matches = [f for f in inventory if safe and f['path'].casefold()==path.casefold()]
    if len(matches)>1: raise ValueError('Ambiguous source file')
    if not matches: return None
    file=matches[0]; source=(root/file['path']).resolve()
    if not source.is_relative_to(root): raise ValueError('Source escapes medium')
    data=source.read_bytes()
    if len(data)!=file['size'] or hashlib.sha256(data).hexdigest()!=file['sha256']:
        raise ValueError('Source file changed')
    return file


def qualify(w, inventory, root, medium):
    if medium not in MEDIA: raise ValueError('Unsupported medium')
    def action(frame):
        key=(int.from_bytes(frame.main_channels[:2],'big'),int.from_bytes(frame.main_channels[2:4],'big'))
        return w.links.members.get(key)
    def nav(frame, destination):
        hits=[]
        for sp in frame.sprites:
            link=w.links.resolve(sp) if sp.kind else None
            if destination in go_targets(link,b'mouseup'):
                hits.append({**w.location(frame,sp,link),'destination':raw_value(destination)})
        if len(hits)!=1: raise ValueError('Missing or ambiguous menu binding')
        return hits[0]
    def txt(frame,channel):
        value=w.text(frame,channel)
        if not value or not value['text']['cp1252_view'].strip():raise ValueError('Missing source text')
        return value
    main=w.frame(b'Knap0');targets=go_targets(action(main),b'enterframe')
    archive=w.frame(b'Arkivet');guide=w.frame(b'Guider')
    # label, title channel, description channel, launch channel, main selector,
    # section, section navigation (or frame selector), artwork frame/channel.
    rows=[(b'A14',16,28,24,b'Knap4',b'Arkivet',b'A12',52,18),
          (b'A24',20,16,23,b'Knap4',b'Arkivet',b'A23',52,18),
          (b'A34',19,20,24,b'Knap4',b'Arkivet',b'A33',52,18),
          (b'A44',19,15,23,b'Knap4',b'Arkivet',b'A43',52,18),
          (b'A54',20,13,23,b'Knap4',b'Arkivet',b'A53',52,18),
          (b'Kl4',9,22,7,b'Knap6',b'Klassisk',b'Kl4',58,18)]
    for i in range(2,7): rows.append((f'G{i}'.encode(),11,15 if i==2 else 13,14+i,b'Knap9',b'Guider',f'G{i}'.encode(),61,18))
    entries=[]
    for label,title_ch,desc_ch,launch_ch,menu,section,select,art_frame,art_ch in rows:
        if menu not in targets:raise ValueError('Section not selected by main menu')
        main_nav=nav(w.frame(menu),section);detail=w.frame(label)
        title=txt(detail,title_ch);description=txt(detail,desc_ch)
        if label==b'Kl4' and title['text']['cp1252_view'].strip()!=MEDIA[medium]:raise ValueError('Wrong classic profile')
        if label.startswith(b'A'):
            section_nav=nav(archive,select)
            if label not in go_targets(action(detail),b'enterframe'):raise ValueError('Installer not in section selector')
        else:
            section_nav={'frame':w.frame(section).number,'destination':raw_value(select)}
            if label not in go_targets(action(detail),b'enterframe'):raise ValueError('Detail not in section selector')
        sp=detail.sprites[launch_ch-1];link=w.links.resolve(sp) if sp.kind else None
        names={b'baopenfile'} if label.startswith(b'G') else {b'barunprogram',b'bashell'}
        launches=calls(link,names,b'mouseup')
        if len(launches)!=1:raise ValueError('Missing or ambiguous primary launch')
        call=launches[0]
        if names=={b'baopenfile'}:
            if len(call.arguments)!=2 or call.arguments[1].lower()!=b'normal':raise ValueError('Unsupported document call')
            path=relative_target(call.arguments[0])
        else:path=launch_path(call)
        file=resolve_file(path,inventory,root)
        continuation=None; continuation_file=None
        if label==b'Kl4':
            nav(detail,b'KChicken')
            warning=w.frame(b'KChicken'); wsp=warning.sprites[90]; wl=w.links.resolve(wsp)
            wc=calls(wl,{b'barunprogram',b'bashell'},b'mouseup')
            if len(wc)!=1: raise ValueError('Missing classic continuation')
            wp=launch_path(wc[0]); continuation={**w.location(warning,wsp,wl),'path':wp,'arguments':[raw_value(a) for a in wc[0].arguments]}
            continuation_file=resolve_file(wp,inventory,root)
        issues=[] if file else ['missing_launch_file']
        if continuation and continuation['path'].casefold()!=path.casefold():issues.append('conflicting_launch_targets')
        evidence={'main_menu':main_nav,'section_navigation':section_nav,'title':title,'description':description,
                  'primary_launch':{**w.location(detail,sp,link),'script':link.script.resource_id,'call_offset':call.offset,
                    'path':path,'arguments':[raw_value(a) for a in call.arguments]},
                  'selection':{'navigation':{'frame':art_frame,'channel':art_ch},'method':'original section menu illustration'},
                  'description_source':description,'frame_action':{'frame':detail.number}}
        if continuation:evidence['warning_continue']=continuation
        referenced={'launch':{**file,'exists':True,'resolved_path':file['path']}} if file else {}
        if continuation_file:referenced['warning_launch']={**continuation_file,'exists':True,'resolved_path':continuation_file['path']}
        records={f['path']:f for f in [file,continuation_file] if f}
        entries.append({'source_id':'Feature'+(b'Menu'+label).hex(),'raw':{},
            'normalized':{'title':title['text']['cp1252_view'].strip(),'description':description['text']['cp1252_view'],
                'version':None,'installer':None,'run':None,'categories':[], 'requirements':{'cpu':{'interpretation':None}}},
            'evidence':evidence,'interpretations':{'selection':'Bounded Norwegian menu text and literal primary control',
                'artwork':'Original section menu illustration; not a program logo or screenshot',
                'content_identity_scope':'resolved literal launch files only, not software package',
                'limitations':['Runtime conditions, animations and click priority are not executed.','Menu title versions are source text, not curated software identity.']},
            'issues':issues,'files':{'referenced':referenced,'discovered':{},'inventory_refs':list(records)},
            'content_identity':build_content_identity([FileRecord(**f) for f in records.values()])})
    return entries


def observe(root, inventory, *, medium, context=None):
    context={} if context is None else context
    result=observe_workshop(root,inventory,context=context)
    result['entries']=qualify(context['workshop'],result['file_inventory'],Path(root).resolve(),medium)
    result['generator']['version']='menu-sections-1'
    result['source']['profile']='additive Norwegian archive/classic/guides; '+medium
    result['source']['limitations']=['Static bound sections only; no runtime execution or whole-disc completeness claim']
    result['validation']={'valid':not any(e['issues'] for e in result['entries']),
        'entry_issues':[{'source_id':e['source_id'],'issues':e['issues']} for e in result['entries'] if e['issues']]}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source_root',type=Path);p.add_argument('inventory',type=Path)
    p.add_argument('--medium',choices=MEDIA,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--images',type=Path)
    a=p.parse_args()
    for target in (a.output,a.images):
        if target is not None and (target.exists() or target.is_symlink() or target.resolve().is_relative_to(a.source_root.resolve())):
            p.error('Outputs must be new and outside source media')
    context={};result=observe(a.source_root,a.inventory,medium=a.medium,context=context);write_manifest(result,a.output,overwrite=False)
    if a.images:
        from .workshop_images import extract
        extract(a.output,context,a.images,selection_rule='original menu illustration of the bound section, not program artwork')
    print(a.medium,len(result['entries']),'source posts')
if __name__=='__main__':main()
