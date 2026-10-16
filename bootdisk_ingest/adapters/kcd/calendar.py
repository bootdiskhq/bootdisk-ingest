"""Preserve explicit J.DTX calendar entries; numeric Type is not interpreted."""
import base64
import configparser
import hashlib
from pathlib import Path, PurePosixPath
import re
from bootdisk_ingest.inventory import get_file_record


def parse_calendar(root, inventory):
    from .parser import build_entry
    metadata = get_file_record(inventory, 'J.DTX')
    if not metadata.get('exists'):
        return [], None
    relative = metadata.get('resolved_path', 'J.DTX')
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Calendar metadata escapes source')
    raw = path.read_bytes()
    if len(raw) != metadata['size'] or hashlib.sha256(raw).hexdigest() != metadata['sha256']:
        raise ValueError('Calendar metadata changed after inventory')
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(raw.decode('cp1252'))
    if parser.defaults():
        raise ValueError('Calendar defaults are not qualified')
    entries, skipped = [], []
    for section in parser.sections():
        if section == 'Generelt':
            continue
        if not re.fullmatch(r'J[1-9][0-9]*', section):
            skipped.append(section)
            continue
        values = dict(parser[section])
        if not values.get('Titel', '').strip() or not values.get('Folder', '').strip():
            raise ValueError('Calendar entry lacks title or folder')
        for field in ('Folder', 'Setup', 'Run'):
            value = values.get(field, '').strip().replace('\\', '/')
            if value and (PurePosixPath(value).is_absolute() or '..' in value.split('/')
                          or ':' in value or value == '.' or any(ord(c) < 32 for c in value)):
                raise ValueError('Unsafe calendar path')
        entry = build_entry(inventory, section, values)
        entry['normalized']['categories'] = []
        entry['evidence'] = {'calendar_metadata': {'path': relative, 'sha256': metadata['sha256'],
                                                   'section': section, 'title_field': 'Titel'}}
        entry['interpretations']['calendar'] = 'J.DTX source post; Type preserved without category inference'
        entries.append(entry)
    return entries, {'path': 'J.DTX', 'resolved_path': relative, 'encoding': 'cp1252',
        'size': len(raw), 'sha256': metadata['sha256'], 'raw_base64': base64.b64encode(raw).decode('ascii'),
        'sections': {s: dict(parser[s]) for s in parser.sections()}, 'defaults': {},
        'parser_warnings': [], 'projected_entry_ids': [e['source_id'] for e in entries],
        'unprojected_sections': skipped}
