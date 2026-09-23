"""Bounded plain-text observation of the ANSI RTF profile used by K-CD.

No rendering, links, fields, objects or external files are evaluated. Original
bytes remain authoritative. Unsupported encodings and malformed groups fail.
"""
import re

METHOD = "rtf-ansi-text-1"
DESTINATIONS = set("fonttbl colortbl stylesheet info pict object filetbl listtable listoverridetable header headerl headerr footer footerl footerr footnote annotation fldinst datastore themedata colorschememapping generator".split())
SYMBOLS = {"par": "\n", "line": "\n", "tab": "\t", "emdash": "—", "endash": "–",
           "bullet": "•", "lquote": "‘", "rquote": "’", "ldblquote": "“", "rdblquote": "”"}
TOKEN = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\([^\r\n])|([{}])|([^\\{}])", re.DOTALL)


def plain_text(raw):
    if len(raw) > 1024 * 1024 or not raw.startswith(b"{\\rtf1"):
        raise ValueError("unsupported RTF header or size")
    text = raw.decode("latin1")
    stack, output, fonts = [], [], {}
    state = {"skip": False, "hidden": False, "destination": None, "font": 0, "uc": 1}
    fallback, default_font, end = 0, 0, 0

    def emit(value, encoded=False):
        nonlocal fallback
        if fallback:
            fallback -= 1
            return
        if not state["skip"] and not state["hidden"]:
            if encoded and fonts.get(state["font"], 0) not in (0, 1):
                raise ValueError("unsupported RTF font charset")
            output.append(value)

    for match in TOKEN.finditer(text):
        if match.start() != end:
            raise ValueError("invalid RTF escape")
        end = match.end()
        word, arg, hexbyte, symbol, brace, char = match.groups()
        if brace == "{":
            if len(stack) >= 128:
                raise ValueError("RTF nesting limit")
            stack.append(state.copy())
        elif brace == "}":
            if not stack:
                raise ValueError("unbalanced RTF groups")
            state = stack.pop(); fallback = 0
        elif char:
            if char in "\r\n":
                continue
            if not stack:
                if char.strip(): raise ValueError("text outside RTF group")
                continue
            emit(char.encode("latin1").decode("cp1252"), encoded=True)
        elif hexbyte:
            emit(bytes.fromhex(hexbyte).decode("cp1252"), encoded=True)
        elif symbol:
            if symbol == "*": state["skip"] = True
            elif symbol in "\\{}": emit(symbol)
            elif symbol == "~": emit("\u00a0")
            elif symbol == "_": emit("\u2011")
            elif symbol == "-": emit("\u00ad")
        elif word:
            number = int(arg) if arg is not None else None
            if word == "bin" or word in ("mac", "pc", "pca", "upr", "fromhtml"):
                raise ValueError("unsupported RTF encoding or binary content")
            if word == "ansicpg" and number != 1252:
                raise ValueError("unsupported RTF code page")
            if word in DESTINATIONS:
                state["skip"] = True; state["destination"] = word
            elif word == "deff": default_font = number
            elif word == "f": state["font"] = number
            elif word == "fcharset" and state["destination"] == "fonttbl":
                fonts[state["font"]] = number
            elif word == "plain": state["font"] = default_font
            elif word == "uc":
                if number is None or not 0 <= number <= 16: raise ValueError("invalid RTF Unicode fallback")
                state["uc"] = number
            elif word == "u":
                if number is None or not -32768 <= number <= 65535: raise ValueError("invalid RTF Unicode value")
                value = number & 65535
                if 0xd800 <= value <= 0xdfff: raise ValueError("unsupported RTF surrogate")
                emit(chr(value)); fallback = state["uc"]
            elif word in SYMBOLS: emit(SYMBOLS[word])
            elif word == "v": state["hidden"] = number != 0
    if end != len(text) or stack:
        raise ValueError("truncated RTF")
    return "".join(output)
