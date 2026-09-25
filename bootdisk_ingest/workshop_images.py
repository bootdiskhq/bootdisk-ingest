"""Preserve workshop shelf artwork with exact resource and container evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from .director_images import bitmap_layout
from .formats.director import DirectorError
from .formats.director.binary import View


def extract(manifest_path, context, output):
    raw=Path(manifest_path).read_bytes();manifest=json.loads(raw);ref='sha256:'+hashlib.sha256(raw).hexdigest()
    w=context['workshop'];archives=context['archives'];sources={s['path']:{k:s[k] for k in ('path','size','sha256')} for s in context['sources']}
    bindings={b['library']:b['source_path'] for b in context['bindings']}
    blobs={};assets=[];outcomes=[]
    def resource(library,rid,tag):
        path=bindings[library];a=archives[path];r=a.resource(rid,tag);data=a.payload(rid,tag);digest=hashlib.sha256(data).hexdigest();blobs[digest]=data
        record={'container':sources[path],'resource_id':rid,'tag':tag,'sha256':digest,'size':len(data),'object_path':'resources/'+digest}
        if a._payloads is None:
            record['offset']=r.offset+8
        elif rid in a._locations:
            record.update(a._locations[rid])
        else:
            offset,size,expanded,codec,_=a._compressed[rid]
            record['offset']=a._base+offset
            if codec==0:record.update(compression='zlib',compressed_size=size,expanded_size=expanded,payload_offset=0)
        return record
    def child(link,tag):
        a=archives[bindings[link.library]];matches=[k.child for k in a.keys() if k.parent==link.cast.resource_id and k.tag==tag]
        if len(matches)!=1:raise DirectorError('Missing or ambiguous workshop image resource')
        return resource(link.library,matches[0],tag)
    for entry in manifest['entries']:
        selection=entry['evidence']['selection'];nav=selection['navigation'];frame=w.frames[nav['frame']-1];sprite=frame.sprites[nav['channel']-1];link=w.links.resolve(sprite)
        try:
            if not link or link.cast.kind!=1:raise DirectorError('Workshop shelf artwork is not a bitmap')
            v=View(link.cast.data,'workshop bitmap');direct=v.span(23,1)[0]==32
            if direct:
                top,left,bottom,right=[v.i16(p) for p in (2,4,6,8)]
                width,height=right-left,bottom-top;stride=v.u16(0)&0x3fff
                v.require(bool(v.u16(0)&0x8000) and 0<width<=1024 and stride==width*4 and 0<height<=4096 and stride*height<=16*1024*1024,0,'invalid direct-color layout')
                layout={'width':width,'height':height,'row_stride':stride,'palette_library':0,'palette_member':0}
            else:
                layout=bitmap_layout(link.cast.data)
            lib=layout['palette_library'];number=layout['palette_member']
            palettes=[p for (l,n),p in w.links.members.items() if n==number and p.cast.kind==4 and (lib==0 or l==(link.library if lib==-1 else lib))]
            if not direct and len(palettes)!=1:raise DirectorError('Missing or ambiguous shelf palette')
            palette=None if direct else child(palettes[0],'CLUT')
            if palette is not None and palette['size']!=1536:raise DirectorError('Incomplete shelf palette')
            assets.append({'entry_source_id':entry['source_id'],'entry_title':entry['normalized']['title'],'kind':'icon',
                'source_ref':{'manifest':ref,'entry':entry['source_id']},
                'selection':{**w.location(frame,sprite,link),'rule':'artwork of the same shelf sprite whose behavior selects the workshop destination'},
                'pixels':child(link,'BITD'),'palette':palette,'metadata':resource(link.library,link.cast.resource_id,'CASt'),
                'raster':{'width':layout['width'],'height':layout['height'],'row_stride':layout['row_stride'],
                          'encoding':'argb32-d6-rle257-or-raw' if direct else 'indexed8-rle257-or-raw','palette_encoding':'rgb16be-high-byte'}})
            issues=['no_separate_program_screenshot_selected']
        except DirectorError as error:
            issues=[str(error)]
        outcomes.append({'entry':entry['source_id'],'issues':issues})
    report={'schema':'bootdisk-embedded-images-1','method':'kcd-workshop-shelf-images-1','manifest':ref,'sources':list(sources.values()),'assets':assets,'outcomes':outcomes}
    output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise DirectorError('Image output must be new')
    output.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.workshop-images-',dir=output.parent))
    try:
        (stage/'resources').mkdir();(stage/'containers').mkdir()
        for path,a in archives.items():(stage/'containers'/sources[path]['sha256']).write_bytes(a.data)
        for digest,data in blobs.items():(stage/'resources'/digest).write_bytes(data)
        (stage/'images.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        os.rename(stage,output)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return report
