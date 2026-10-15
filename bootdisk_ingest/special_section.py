"""Preserve the explicit Speciel/SpecielTekst source post on K-CD 15/2001.

No standalone installer or runtime menu binding is inferred from the folder.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from .core.identity import build_content_identity
from .core.inventory import FileRecord
from .output import write_manifest


def observe(root, manifest_path):
    root=Path(root).resolve();raw=Path(manifest_path).read_bytes();base=json.loads(raw)
    fields=base['source']['sections'].get('Generelt',{})
    if fields.get('Speciel')!='PC-ens driftsutgifter' or not fields.get('SpecielTekst'):
        raise ValueError('Unsupported special section')
    inventory=base['file_inventory']
    def verified(name):
        hits=[f for f in inventory if f['path'].casefold()==name.casefold()]
        if len(hits)!=1:raise ValueError('Missing or ambiguous source evidence')
        f=hits[0];p=(root/f['path']).resolve()
        if not p.is_relative_to(root):raise ValueError('Source escapes medium')
        b=p.read_bytes()
        if len(b)!=f['size'] or hashlib.sha256(b).hexdigest()!=f['sha256']:raise ValueError('Source evidence changed')
        return f,b
    metadata,_=verified('K.DTX');executable,code=verified('K.EXE')
    observations=[]
    for token in [b'PCkWhTotal',b'KWhPris',b'KWhChange',b'TotalWattForbrugChange']:
        position=code.find(token)
        if position<0:raise ValueError('Missing cost-form observation')
        observations.append({'offset':position,'literal':token.decode('ascii')})
    icon,_=verified('Speciel/Ikon.bmp');illustration,_=verified('Speciel/Shot.jpg')
    entry={'source_id':'Feature'+b'Speciel'.hex(),'raw':dict(fields),
        'normalized':{'title':fields['Speciel'],'description':fields['SpecielTekst'],'folder':'Speciel',
            'version':None,'installer':None,'run':None,'categories':[], 'requirements':{'cpu':{'interpretation':None}}},
        'interpretations':{'selection':'Explicit Generelt.Speciel and SpecielTekst source metadata',
            'limitations':['No standalone program file exists in Speciel; no installer or external program identity is inferred.',
                'Cost-form literals in K.EXE are container observations, not proof of runtime menu dispatch.',
                'Speciel/Shot.jpg is an editorial wallet illustration, not a runtime screenshot.']},
        'evidence':{'metadata_container':metadata,'metadata_section':'Generelt','title_field':'Speciel','description_field':'SpecielTekst',
            'menu_container':executable,'cost_form_literals':observations},'issues':[],
        'files':{'referenced':{},'discovered':{'icon':{**icon,'exists':True,'is_file':True},
            'screenshot':{**illustration,'exists':True,'is_file':True}},'inventory_refs':[icon['path'],illustration['path']]},
        'content_identity':build_content_identity([FileRecord(**icon),FileRecord(**illustration)])}
    result=copy.deepcopy(base);result['entries']=[entry]
    result['generator']['version']='special-section-1'
    result['source']['profile']='bounded K-CD 15/2001 special metadata; not standalone software'
    result['source']['previous_manifest']='sha256:'+hashlib.sha256(raw).hexdigest()
    result['validation']={'valid':True,'entry_issues':[]}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('manifest',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--extraction',type=Path)
    a=p.parse_args()
    for target in (a.output,a.extraction):
        if target and (target.exists() or target.is_symlink() or target.resolve().is_relative_to(a.root.resolve())):p.error('Outputs must be new and outside source media')
    m=observe(a.root,a.manifest);write_manifest(m,a.output,overwrite=False)
    if a.extraction:
        from .extraction import extract_entries
        extract_entries(a.root,m,a.extraction)
if __name__=='__main__':main()
