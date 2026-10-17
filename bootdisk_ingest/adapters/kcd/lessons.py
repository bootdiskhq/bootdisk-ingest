"""Preserve qualified workshop lesson documents, separately from program rows."""
import base64
import configparser
import hashlib
from pathlib import Path, PurePosixPath
import re
from .dtx_text import ini_projection

PATH = re.compile(r'Tools/(?:[^/]+/)?Data(?:DK|Fi|No|Sv)?\.dtx', re.I)
SECTION = re.compile(r'(?:Generelt|Intro|Outtro|L[0-9]+)\Z')


def observe_lessons(root, inventory, entries):
    documents = []
    for item in inventory['files']:
        relative = item['path']
        if not PATH.fullmatch(relative):
            continue
        path = Path(root)/relative
        if not path.resolve().is_relative_to(Path(root).resolve()):
            raise ValueError('Lesson metadata escapes media')
        data = path.read_bytes()
        if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Lesson metadata changed after inventory')
        text, continuations = ini_projection(data.decode('cp1252'))
        parser = configparser.ConfigParser(interpolation=None, strict=False);parser.optionxform=str
        parser.read_string(text)
        sections = {s:dict(parser[s]) for s in parser.sections()}
        # A filename alone never establishes the document role.
        recognized = (any(re.fullmatch(r'L[0-9]+', s) for s in sections)
                      or bool(sections.get('Generelt', {}).get('ProgramNavn')))
        if not recognized:
            continue
        folder = str(PurePosixPath(relative).parent)
        associated = [e['source_id'] for e in entries
                      if (e['normalized'].get('folder') or '').casefold() == folder.casefold()]
        suffix = PurePosixPath(relative).stem[4:].casefold()
        documents.append({'path':relative,'resolved_path':relative,'encoding':'cp1252',
            'sha256':item['sha256'],'size':len(data),'raw_base64':base64.b64encode(data).decode(),
            'sections':sections,'defaults':dict(parser.defaults()),
            'role':'workshop_lesson_document','language_hint':{'no':'nb-NO','dk':'da','sv':'sv','fi':'fi'}.get(suffix),
            'text_projection':{'method':'dtx-prose-continuation-1','continuation_lines':continuations},
            'projected_entry_ids':[], 'associated_entry_ids':associated,
            'association_scope':'Same source folder only; no software identity or launch claim',
            'unprojected_sections':[s for s in sections if not SECTION.fullmatch(s)],
            'publication_status':'preserved_only',
            'limitations':['Lesson UI, images, navigation and language completeness are not certified.',
                           'No additional program row or executable association is inferred.']})
    return documents
