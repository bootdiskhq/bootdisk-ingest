"""Bounded static profile for three K-CD 1/2000 feature sections. Never executes Lingo."""
from pathlib import Path
import argparse,json,hashlib
from .legacy_tools import observe as observe_workshop
from .core.identity import build_content_identity
from .core.inventory import FileRecord
from .output import write_manifest

def qualify(w, inventory, root):
 from bootdisk_ingest.adapters.kcd.director import calls,go_targets,launch_path,raw_value
 def frame(label):
  nums=w.labels.get(label,[])
  if len(nums)!=1:raise ValueError('Missing or ambiguous label '+repr(label))
  return w.frames[nums[0]-1]
 def action(f):
  key=(int.from_bytes(f.main_channels[:2],'big'),int.from_bytes(f.main_channels[2:4],'big'))
  return w.links.members.get(key)
 def button(f,destination):
  hits=[]
  for sp in f.sprites:
   if not sp.kind:continue
   link=w.links.resolve(sp)
   if destination in go_targets(link,b'mouseup'):hits.append((sp,link))
  if len(hits)!=1:raise ValueError('Missing or ambiguous navigation button')
  sp,link=hits[0];return {'frame':f.number,'channel':sp.channel,'library':link.library,'member':link.member,'script':link.script.resource_id,'destination':raw_value(destination)}
 def launch(f, primary_channel=None):
  hits=[]
  for sp in f.sprites:
   if not sp.kind:continue
   link=w.links.resolve(sp)
   for c in calls(link,{b'barunprogram',b'bashell'},b'mouseup'):
    path=launch_path(c);hits.append({'path':path,'frame':f.number,'channel':sp.channel,'library':link.library,'member':link.member,'script':link.script.resource_id,'call_offset':c.offset})
  primary=[h for h in hits if primary_channel is None or h['channel']==primary_channel]
  other=[h for h in hits if h not in primary]
  if len(primary)!=1:raise ValueError('Missing or ambiguous launch button')
  return primary[0],other
 main=frame(b'Knap0');main_targets=go_targets(action(main),b'enterframe')
 profile=[('Toonworks',b'Knap2',b'Edutainment',b'E2',b'E4',b'BChicken',25,24),('PicturesToExe',b'Knap5',b'Multimedie',b'M2',b'M4',b'NChicken',15,8),('WindowBlinds',b'Surprise',b'Overraskelsen',b'O2',b'O4',b'OChicken',14,10)]
 entries=[]
 for name,menu,section,selector,install,warning,heading_channel,description_channel in profile:
  if menu not in main_targets:raise ValueError('Main menu does not reference section button')
  nav=button(frame(menu),section);start=frame(section);select=frame(selector);detail=frame(install)
  if not start.number<=select.number<=detail.number:raise ValueError('Unexpected section frame order')
  if install not in go_targets(action(select),b'enterframe'):raise ValueError('Section selector does not reference installer state')
  if action(select)!=action(detail):raise ValueError('Installer state uses unrelated action')
  direct,direct_other=launch(detail);warn=button(detail,warning);continuation,warning_other=launch(frame(warning),91)
  if direct['path'].casefold()!=continuation['path'].casefold():raise ValueError('Conflicting direct/warning launch targets')
  matches=[f for f in inventory if f['path'].casefold()==direct['path'].casefold()]
  if len(matches)!=1:raise ValueError('Missing or ambiguous source file')
  file=matches[0];source=(root/file['path']).resolve()
  if not source.is_relative_to(root):raise ValueError('Launch escapes source root')
  data=source.read_bytes()
  if len(data)!=file['size'] or hashlib.sha256(data).hexdigest()!=file['sha256']:raise ValueError('Source file changed')
  heading=w.text(detail,heading_channel);description=w.text(detail,description_channel)
  if not heading or heading['text']['cp1252_view'].strip()!=name or not description:raise ValueError('Unexpected title/description binding')
  entries.append({'source_id':'Feature'+section.hex(),'normalized':{'title':name,'description':description['text']['cp1252_view'],'version':None},'evidence':{'main_selector':{'frame':main.number,'script':action(main).script.resource_id,'target':raw_value(menu)},'menu_button':nav,'section_entry_frame':start.number,'section_selector_frame':select.number,'installer_frame':detail.number,'title':heading,'description':description,'direct_launch':direct,'warning_button':warn,'warning_continue':continuation,'other_launch_controls':direct_other+warning_other,'warning_association':'K-CD profile convention: channel 91; not a runtime hit-test result'},'file':file,'interpretation':'Static score-bound feature section, not runtime execution proof','limitations':['Section-entry animation/timeline progression is not evaluated.','Warning page also contains a shared Heart/Setup.exe control on channel 16. Runtime overlay and click priority are not evaluated.','Program version and distribution are not inferred from filenames.']})
 return entries


def observe(source_root, inventory_manifest, *, context=None):
    context = {} if context is None else context
    base = observe_workshop(source_root, inventory_manifest, context=context)
    rows = qualify(context['workshop'], base['file_inventory'], Path(source_root).resolve())
    entries = []
    # Original section illustrations, not program logos or screenshots.
    artwork = [(46,18),(55,18),(130,5)]
    for row, (frame, channel) in zip(rows, artwork):
        file = row['file']
        evidence = row['evidence']
        evidence['selection'] = {'navigation': {'frame': frame, 'channel': channel},
            'method': 'qualified section illustration; not a program logo'}
        evidence['description_source'] = evidence['description']
        evidence['frame_action'] = {'frame': evidence['installer_frame']}
        entries.append({'source_id': row['source_id'], 'raw': {},
            'normalized': {**row['normalized'], 'installer': None, 'run': None,
                'categories': [], 'requirements': {'cpu': {'interpretation': None}}},
            'interpretations': {'selection': row['interpretation'],
                'limitations': row['limitations'],
                'artwork': 'Original section illustration; not a program logo or screenshot',
                'content_identity_scope': 'resolved literal launch files only, not software package'},
            'evidence': evidence,
            'issues': ['shared_warning_control_not_runtime_tested'],
            'files': {'referenced': {'launch': {**file, 'exists': True, 'resolved_path': file['path']}},
                'discovered': {}, 'inventory_refs': [file['path']]},
            'content_identity': build_content_identity([FileRecord(**file)])})
    base['generator']['version'] = 'feature-sections-1'
    base['source']['profile'] = 'additive K-CD 1/2000 feature sections; feature-sections-1'
    base['source']['navigation'] = [r['evidence']['menu_button'] for r in rows]
    base['source']['limitations'] = ['Bounded static profile, not runtime or whole-disc completeness',
        'Shared warning controls retained; channel 91 association follows existing K-CD convention']
    base['entries'] = entries
    base['validation'] = {'valid': False, 'entry_issues': [
        {'source_id': e['source_id'], 'issues': e['issues']} for e in entries]}
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    parser.add_argument('inventory_manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--images', type=Path)
    args = parser.parse_args()
    for target in (args.output, args.images):
        if target is not None and (target.exists() or target.is_symlink() or
                target.resolve().is_relative_to(args.source_root.resolve())):
            parser.error('Outputs must be new and outside source media')
    context = {}
    result = observe(args.source_root, args.inventory_manifest, context=context)
    write_manifest(result, args.output, overwrite=False)
    if args.images:
        from .workshop_images import extract
        extract(args.output, context, args.images,
                selection_rule='original illustration in the qualified program section; not a program logo or screenshot')
    print('Feature source posts:', len(result['entries']))

if __name__ == '__main__':
    main()
