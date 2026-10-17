"""Observe unindented prose continuation in qualified DTX text fields.

Only the INI projection receives indentation. Original bytes remain authoritative.
Newline/repeated text is retained; unknown malformed fields still fail parsing.
"""
import re

PROSE = re.compile(r'(?:Instruks(?:No|DK|Sv|Fi)|Global(?:NO|DK|SV|FI)?|VTekst|IntroTekst|UnderTitel|Videre|Tekst\d+)', re.I)
ASSIGNMENT = re.compile(r'^\s*([^\s=:\[\]]+)\s*[=:]')


def ini_projection(text):
    result = [];field = None;continued = []
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        stripped = line.strip()
        if stripped.startswith('['):
            field = None
        elif stripped and not stripped.startswith((';', '#')):
            assignment = ASSIGNMENT.match(line)
            if assignment:
                field = assignment.group(1)
            elif field and PROSE.fullmatch(field) and not line.startswith((' ', '\t')):
                line = '\t' + line
                continued.append(number)
        result.append(line)
    return ''.join(result), continued
