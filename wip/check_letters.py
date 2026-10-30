"""Independent letters-and-digits check of every version against its Legisla Goiás record (regex tokenizer, no HTML
parser).

    python -X utf8 check_letters.py [part.json ...]

For each version: the record's "conteudo" with every text run that is struck through (s, strike, del, or a
line-through style anywhere above it), in red, in Arial Black or in green (nearest colour and font family set above it)
left out, and the publisher's note lines (starting "- Redação", "- Acrescido", ...) left out, reduced to letters and
digits, must equal the version's unit files reduced the same way, each unit found at its place in document order.
"""
import hashlib, html, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from br_lib import letters_check  # noqa: E402

TOKEN = re.compile(r'<!--.*?-->|<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*)>|([^<]+)', re.S)
VOIDS = ('br', 'img', 'meta', 'link', 'hr', 'input', 'col', 'area', 'base', 'wbr')
BREAKS = ('p', 'div', 'br', 'tr', 'li', 'table', 'tbody', 'thead', 'ul', 'ol', 'center', 'blockquote', 'h1', 'h2', 'h3',
          'h4', 'h5', 'h6')
NOTE = re.compile(r'(?m)^\s*-\s*(?:Reda|Acresc|Revog|Vide|Renumer|Supr|Alter|Inclu|Declar|Suspen|Regulam|Ver\b|Veja|'
                  r'Efic|ADI|Express|Texto|Vig|Prorrog|Nova|Com |Promulg|Retific|Republic|Derrog|Transform|'
                  r'Modific|Ac[óo]rd|Decis|Liminar|Mantid|Restab|Repristin|Obs|Nota).*$', re.I)


def attr(a, name):
    m = re.search(r'(?i)\b' + name + r'\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))', a)
    return (m.group(2) or m.group(3) or m.group(4) or '') if m else ''


def page_text(h):
    h = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->|<head\b.*?</head>', '', h)
    i = h.lower().find('<body')
    h = h[h.index('>', i) + 1:] if i >= 0 else h
    open_, out = [], []
    for m in TOKEN.finditer(h):
        close, tag, a, text = m.group(1), (m.group(2) or '').lower(), m.group(3) or '', m.group(4)
        if text is not None:
            strike = any(o[1] for o in open_)
            color = ([o[2] for o in open_ if o[2]] or [''])[-1].lower()
            face = ([o[3] for o in open_ if o[3]] or [''])[-1].lower()
            red = color in ('red', '#ff0000', '#f00') or re.fullmatch(r'rgb\(\s*255\s*,\s*0\s*,\s*0\s*\)', color)
            if not (strike or red or 'arial black' in face or color in ('green', '#008000')):
                out.append(re.sub(r'\s+', ' ', html.unescape(text)))
            continue
        if not tag:
            continue
        if tag in BREAKS:
            out.append('\n')
        if close:
            for k in range(len(open_) - 1, -1, -1):
                if open_[k][0] == tag:
                    del open_[k:]
                    break
        elif tag not in VOIDS and not a.rstrip().endswith('/'):
            st = attr(a, 'style').lower()
            cs = re.findall(r'(?:^|[;\s"])color\s*:\s*([^;]+)', st)
            fs = re.findall(r'font-family\s*:\s*([^;]+)', st)
            open_.append((tag, tag in ('s', 'strike', 'del') or 'line-through' in st,
                          (cs[-1] if cs else attr(a, 'color')).strip().strip('"\''),
                          (fs[-1] if fs else attr(a, 'face')).strip()))
    s = re.sub(r'[ \t\r\f\v\xa0]+', ' ', ''.join(out))
    s = re.sub(r'(?im)^\s*Este texto n[ãa]o substitui o publicad.*$', '', s)  # the publisher's notice
    return NOTE.sub('', s)


def main(paths):
    vs = []
    for p in paths:
        for a in json.load(open(p, encoding='utf-8'))['acts']:
            for v in a['versions']:
                raw = (HERE / '.cache' / 'raw' / hashlib.sha256(v['source_url'].encode()).hexdigest()).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == v['sha256'], (a['slug'], 'sha256')
                vs.append((f"{a['slug']} {v['from']}", v['units'], page_text(json.loads(raw)['conteudo'])))
    bad = letters_check(vs, None)
    for b in bad:
        print(b)
    print(f'{len(vs)} versions checked, {len(bad)} mismatches')
    return len(bad)


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1:] or sorted(str(p) for p in (HERE / 'corpus.d').glob('*.json'))) else 0)
