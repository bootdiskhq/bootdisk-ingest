"""Read explicitly bound RTF documents without changing the ingest manifest."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
from .formats.rtf import plain_text

SCHEMA = 'bootdisk-rtf-observations-1'
METHOD = 'rtf-ansi-text-terminal-nul-1'


def collect(manifest_path, root):
    manifest_path, root = Path(manifest_path), Path(root).resolve()
    source = manifest_path.read_bytes()
    manifest = json.loads(source)
    ref = 'sha256:' + hashlib.sha256(source).hexdigest()
    documents, issues = [], []
    for position, entry in enumerate(manifest['entries']):
        file = entry.get('files', {}).get('discovered', {}).get('description_rtf', {})
        if not file.get('exists'):
            continue
        relative = file.get('resolved_path', file.get('path'))
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
            raise ValueError('unsafe RTF path')
        target = root.joinpath(*path.parts).resolve()
        if not target.is_relative_to(root):
            raise ValueError('RTF escapes source root')
        inventory = [f for f in manifest.get('file_inventory', []) if f.get('path') == relative]
        if len(inventory) != 1 or any(file.get(k) != inventory[0].get(k) for k in ('size', 'sha256')):
            raise ValueError('RTF binding differs from inventory')
        key = {'manifest': ref, 'entry': entry['source_id']}
        if file.get('size', 0) > 1024 * 1024:
            issues.append({'key': key, 'path': relative, 'reason': 'RTF exceeds 1 MiB limit'})
            continue
        try:
            raw = target.read_bytes()
        except OSError as exc:
            issues.append({'key': key, 'path': relative, 'reason': str(exc)})
            continue
        if len(raw) != file['size'] or hashlib.sha256(raw).hexdigest() != file['sha256']:
            raise ValueError('RTF source changed since inventory')
        try:
            text = plain_text(raw)
            warning = None
        except (ValueError, UnicodeError) as exc:
            text, warning = None, str(exc)
        documents.append({'key': key, 'pointer': f'/entries/{position}/files/discovered/description_rtf',
                          'path': relative, 'sha256': file['sha256'], 'size': len(raw),
                          'raw_base64': base64.b64encode(raw).decode('ascii'), 'method': METHOD,
                          'text': text, 'warning': warning})
    return {'schema': SCHEMA, 'manifest': ref, 'documents': documents, 'issues': issues}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest'); p.add_argument('source_root'); p.add_argument('--output', required=True)
    a = p.parse_args()
    result = collect(a.manifest, a.source_root)
    with Path(a.output).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')

if __name__ == '__main__': main()
