"""Static observation of the 2012 K-CD HTML template; never execute JS/HTML."""
import base64
import hashlib
import json
import posixpath
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from bootdisk_ingest.inventory import get_file_record, get_folder_records
from bootdisk_ingest.core.identity import build_content_identity
from .parser import normalize_cpu

SCHEMA = 'kcd-html-1'
METHOD = 'kcd-html-menu-1'
CATEGORIES = {'topical':'Aktuelt', 'tools':'Verktøykassa', 'securitycenter':'Sikkerhetssenteret', 'game':'Spill', 'tastes':'Demoer', 'articles':'Artikler', 'videos':'Videokurs'}
ROW = re.compile(r'''cdindex\[(\d+)\]\s*=\s*\{\s*'title'\s*:\s*("(?:[^"\\]|\\.)*"),\s*'url'\s*:\s*'([^']+)',\s*'category'\s*:\s*'([^']+)'\s*\};''')

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
    def find(self, *, tag=None, id=None, cls=None):
        out=[]
        for c in self.children:
            if not isinstance(c, Node): continue
            if (tag is None or c.tag==tag) and (id is None or c.attrs.get('id')==id) and (cls is None or cls in c.attrs.get('class','').split()): out.append(c)
            out.extend(c.find(tag=tag,id=id,cls=cls))
        return out
    def text(self, exclude_links=False):
        if self.tag in ('script','style','input') or (exclude_links and self.tag == 'a' and self.attrs.get('onclick')): return ''
        if self.tag=='br': return '\n'
        return ''.join(c.text(exclude_links) if isinstance(c,Node) else c for c in self.children)

class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(text);self.close()
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs);self.stack[-1].children.append(node)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if self.stack[-1].tag==tag:self.stack.pop()
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,data):self.stack[-1].children.append(data)

def clean(text):
    return '\n'.join(re.sub(r'[^\S\n]+',' ',line).strip() for line in text.splitlines()).strip()

def one(nodes, label):
    if len(nodes)!=1: raise ValueError(f'HTML requires one {label}, found {len(nodes)}')
    return nodes[0]

def local_path(page, href):
    u=urlsplit(href)
    if u.scheme or u.netloc or href.startswith('#'):return None
    value=unquote(u.path)
    if '\\' in value or '\x00' in value or ':' in value or value.startswith('/'):raise ValueError('Unsafe HTML reference')
    value=posixpath.normpath(posixpath.join(posixpath.dirname(page),value))
    if value=='..' or value.startswith('../'):raise ValueError('HTML reference escapes CD')
    return value

def index_rows(raw):
    text=raw.decode('cp1252')
    rows=[]
    remainder=ROW.sub('',text).replace('var cdindex = new Array();','').strip()
    if remainder:raise ValueError('Unqualified cdindex syntax')
    for n,title,url,cat in ROW.findall(text):
        if int(n)!=len(rows) or cat not in CATEGORIES:raise ValueError('Invalid index position/category')
        rows.append({'title':json.loads(title),'url':url,'category':cat})
    if not rows:raise ValueError('Empty CD index')
    return rows

def parse_page(raw, row):
    text=raw.decode('cp1252')
    if not re.search(r'charset=iso-8859-1',text,re.I):raise ValueError('Unqualified HTML encoding')
    tree=Tree(text).root;page=row['url'];group=row['category']
    if group in ('articles','videos'):
        cls='guide' if group=='articles' else 'video'
        candidates=tree.find(cls=cls)
        boxes=[b for b in candidates if clean(one(b.find(cls=cls+'headline'),'headline').text())==clean(row['title'])]
        box=one(boxes,'matching group entry');title=clean(row['title'])
        desc=clean(one(box.find(cls=cls+'desc'),'description').text(exclude_links=True))
        image=one(box.find(tag='img'),'entry image').attrs['src']
        license_value=version=None
    else:
        box=one(tree.find(id='content'),'content');title=clean(one([n for n in box.children if isinstance(n,Node) and n.tag=='h1'],'title').text())
        desc=clean(one(box.find(cls='softwaredesc'),'description').text())
        image=one(box.find(cls='softwareimage'),'entry image').attrs['src']
        details=[clean(n.text()) for n in one(box.find(cls='softwaredetails'),'details').find(tag='li')]
        def value(prefix):
            found=[s[len(prefix):].strip() for s in details if s.startswith(prefix)]
            if len(found)>1:raise ValueError('Duplicate HTML field')
            return found[0] if found else None
        license_value=value('Lisenstype:');version=value('Versjon:')
    if title!=clean(row['title']):raise ValueError('Index/page title mismatch')
    refs=[];external=[]
    for node in box.find():
        href=node.attrs.get('href')
        if href and not href.startswith('#'):
            path=local_path(page,href)
            if path:refs.append(path)
            elif urlsplit(href).scheme in ('http','https'):external.append(href)
        onclick=node.attrs.get('onclick','')
        if onclick:
            # Observe only literal parameters of known template controls.
            match=re.fullmatch(r"window.open\('([^']+)'\);?",onclick)
            video=re.fullmatch(r"show\(\{\s*'width'\s*:\s*\d+,\s*'height'\s*:\s*\d+,\s*'file'\s*:\s*'([^']+)'\s*\}\);?",onclick)
            if not (match or video):raise ValueError('Unqualified inline source control')
            path=local_path(page,(match or video).group(1))
            if path:refs.append(path)
    image=local_path(page,image)
    if not image:raise ValueError('Nonlocal source image')
    return {'title':title,'description':desc,'image':image,'references':list(dict.fromkeys(refs)),'external_links':list(dict.fromkeys(external)), 'license':license_value,'version':version,'category':CATEGORIES[group]}

def parse_disc(root, inventory, *, generated_at=None):
    root=Path(root)
    def document(path):
        rec=get_file_record(inventory,path)
        if not rec.get('is_file'):raise ValueError('Missing HTML source '+path)
        raw=(root/rec.get('resolved_path',path)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=rec['sha256']:raise ValueError('Changed HTML source')
        return {**{k:rec[k] for k in ('path','size','sha256')},'raw_base64':base64.b64encode(raw).decode('ascii'),'encoding':'cp1252','declared_encoding':'iso-8859-1'}
    index=document('scripts/cdindex.js');rows=index_rows(base64.b64decode(index['raw_base64']));documents={'scripts/cdindex.js':index};entries=[]
    for position,row in enumerate(rows):
        page=row['url'];safe=local_path('',page)
        if safe!=page or not page.startswith('html/'):raise ValueError('Unsafe menu page')
        if page not in documents:documents[page]=document(page)
        obs=parse_page(base64.b64decode(documents[page]['raw_base64']),row)
        folder=posixpath.dirname(obs['image']);records=get_folder_records(inventory,folder)
        refs={f'link_{i+1}':get_file_record(inventory,p) for i,p in enumerate(obs['references'])}
        discovered={'screenshot':get_file_record(inventory,obs['image'])}
        entry_id=Path(page).stem if row['category'] not in ('articles','videos') else row['category']+Path(folder).name
        if any(e['source_id']==entry_id for e in entries):raise ValueError('Duplicate HTML entry')
        entries.append({'source_id':entry_id,'raw':{'html_title':obs['title'],'html_description':obs['description']},'normalized':{'title':obs['title'],'short_title':None,'description':obs['description'],'folder':folder,'installer':None,'run':None,'license':obs['license'],'website':None,'requirements':{'cpu':normalize_cpu(None),'ram_mb':None,'disk_mb':None,'directx':None},'requires_network':None,'categories':[obs['category']]},'interpretations':{},'evidence':{'html_menu':{'method':METHOD,'index_position':position,'page':page,'observation':obs}},'files':{'referenced':refs,'discovered':discovered,'inventory_refs':[r['path'] for r in records]},'content_identity':build_content_identity(records)})
    # Require every actual software page and every grouped headline to be accounted for.
    projected={r['url'] for r in rows}
    candidates={f['path'] for f in inventory['files'] if re.fullmatch(r'html/(?:topical|tool|security|game|taste)\d+\.html',f['path'])}
    if candidates-projected:raise ValueError('Unindexed software pages: '+str(sorted(candidates-projected)))
    for category,cls in [('articles','guide'),('videos','video')]:
        page='html/'+category+'.html'
        if get_file_record(inventory,page).get('is_file'):
            if page not in documents:documents[page]=document(page)
            titles=[clean(one(n.find(cls=cls+'headline'),'headline').text()) for n in Tree(base64.b64decode(documents[page]['raw_base64']).decode('cp1252')).root.find(cls=cls)]
            if titles!=[clean(r['title']) for r in rows if r['category']==category]:raise ValueError('Unindexed grouped source entries')
    return {'schema_version':SCHEMA,'generator':{'name':'bootdisk-ingest','version':METHOD,'generated_at':generated_at or datetime.now(timezone.utc).isoformat()},'source':{'format':METHOD,'documents':documents,'coverage':{'profile':METHOD,'index_entries':len(rows),'metadata_files':[{'path':p,'unprojected_sections':[]} for p in documents],'unprocessed_metadata':[],'scope':'Current CD index, software pages, article and video menu entries; not historical magazine search index or executable compatibility'}},'disc':{'raw':{},'content_identity':build_content_identity(inventory['files'])},'entries':entries}
