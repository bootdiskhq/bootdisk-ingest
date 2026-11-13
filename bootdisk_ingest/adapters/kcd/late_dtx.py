"""Bounded source variants on K-CD 13/2001 and 4/2002. Keep physical INI occurrences."""
import base64
import configparser
import hashlib
import re
from pathlib import Path

PIXIA = '93692f2403e5bd1abb31e4d376459a355ed977ac0724bbdf7e7e8030d792e1bf'
QUIZ = 'b9c761add7ddd6051314eb06506d928efe03e597f8a68c0d6d038021592d525a'

def occurrences(text):
    matches=list(re.finditer(r'(?m)^\[([^\]\r\n]+)\][ \t]*\r?$',text))
    result={}
    for i,m in enumerate(matches):
        ini=configparser.ConfigParser(interpolation=None,strict=False);ini.optionxform=str
        ini.read_string(text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)])
        result.setdefault(m[1],[]).append(dict(ini[m[1]]))
    return result

def late_entries(root,inventory,digest,text,general,entries):
    from .parser import build_entry
    docs=[]
    if digest==PIXIA:
        blocks=occurrences(text)
        # Two different K36 titles; three other repeated sections translate the
        # same title. Flytter repeats Pixia's launch fields in Danish.
        for section in ('K36','K38','K39','K42'):
            index=1 if section=='K36' else 0
            entry=build_entry(inventory,section,blocks[section][index])
            entry['evidence']={'physical_section':{'name':section,'index':index}}
            pos=next(i for i,e in enumerate(entries) if e['source_id']==section)
            entries[pos]=entry
        entry=build_entry(inventory,'Flytter',blocks['K36'][0])
        entry['evidence']={'physical_section':{'name':'K36','index':0},'alternate_section':'Flytter'}
        entries.append(entry)
    path='Quiz/Quiz.dtx'
    record=next((f for f in inventory['files'] if f['path']==path),None)
    if record and record['sha256']==QUIZ and digest=='7466a4d886293f3d8ffeee052a77791fbe7e2bf7aae5334ffc1f89ddc0f21144':
        raw=(Path(root)/path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=QUIZ:raise ValueError('Changed quiz data')
        # Preserve question prose verbatim, including unindented continuation lines.
        names=re.findall(r'(?m)^\[([^\]\r\n]+)\][ \t]*\r?$',raw.decode('cp1252'))
        if len(names)!=63 or set(names)!={'General','Svar',*('S'+str(i) for i in range(1,61))}:raise ValueError('Unknown quiz sections')
        entry=build_entry(inventory,'Quiz',{'Titel':general['Quiz'],'Global':general['QuizTekst'],'Folder':'Quiz'})
        entry['raw']=dict(general);entry['evidence']={'quiz_menu':{'section':'Generelt','title':'Quiz','description':'QuizTekst','document':path}}
        entries.append(entry)
        docs.append(dict(record,resolved_path=path,encoding='cp1252',raw_base64=base64.b64encode(raw).decode(),role='quiz_questions_and_answers',publication_status='preserved_only',associated_entry_ids=['Quiz'],projected_entry_ids=[],unprojected_sections=[]))
    return docs
