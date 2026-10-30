"""Builds corpus.d parts for Goiás from the retrieved Casa Civil (Legisla Goiás) API records (no network).

    python -X utf8 parse.py --today YYYY-MM-DD [--only constituicao|lc] [--part-size 50]

Each API record carries the act's compiled text ("conteudo", Word HTML). In it the Casa Civil shows earlier wordings
struck through or in red, each followed by a note such as "- Redação original", and marks every alteration with a
note in Arial Black ("- Redação dada pela Emenda Constitucional nº 46, de 9-9-2010, D.O. de 7-12-2010"); "Vide" notes
are in green. The text in force is what is left once those are taken out. An act with no alteration note is given as
enacted, credited to the act itself; an altered act only as its text in force, credited to the publisher as the oldest
version available, dated by the latest date its alteration notes cite.
"""
import argparse, html, json, re, sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from br_lib import lines_of, units_of, write_part, sha, norm  # noqa: E402

CACHE = HERE / '.cache'
API = 'https://legisla.casacivil.go.gov.br/api/v2/pesquisa/legislacoes'
SITE = 'https://legisla.casacivil.go.gov.br/pesquisa_legislacao'
BLOCK = {'p', 'div', 'br', 'tr', 'li', 'table', 'tbody', 'thead', 'ul', 'ol', 'center', 'blockquote', 'h1', 'h2', 'h3',
         'h4', 'h5', 'h6'}
VOID = {'br', 'img', 'meta', 'link', 'hr', 'input', 'col', 'area', 'base', 'wbr'}
RED = re.compile(r'(?i)^(?:red|#ff0000|#f00|rgb\(\s*255\s*,\s*0\s*,\s*0\s*\))$')
GREEN = re.compile(r'(?i)^(?:green|#008000)$')


def props(tag, attrs):
    """What an element sets itself: (struck, colour, font family); None where it sets nothing."""
    a = dict(attrs)
    style = (a.get('style') or '').lower()
    colors = re.findall(r'(?<![-\w])color\s*:\s*([^;]+)', style) or ([a['color']] if a.get('color') else [])
    fams = re.findall(r'font-family\s*:\s*([^;]+)', style) or ([a['face']] if a.get('face') else [])
    struck = tag in ('s', 'strike', 'del') or 'line-through' in style
    return struck, (colors[-1].strip().strip('"\'') if colors else None), (fams[-1].strip().lower() if fams else None)


class Split(HTMLParser):
    """Splits the compiled HTML into the text in force (kept, with block breaks as <br>) and the removed runs, the way
    a browser shows it: a strike-through applies to everything inside it; colour and font family come from the
    nearest element that sets them."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.kept, self.old, self.notes = [], [], [], []

    def state(self):
        struck = any(e[1] for e in self.stack)
        color = next((e[2] for e in reversed(self.stack) if e[2]), '')
        fam = next((e[3] for e in reversed(self.stack) if e[3]), '')
        if struck or RED.match(color):
            return 'old'
        if 'arial black' in fam or GREEN.match(color):
            return 'note'
        return None

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK:
            self.kept.append('<br>')
        if tag not in VOID:
            self.stack.append((tag, *props(tag, attrs)))

    def handle_endtag(self, tag):
        if tag in BLOCK:
            self.kept.append('<br>')
            if self.notes and self.notes[-1] != '\n':
                self.notes.append('\n')
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, d):
        st = self.state()
        if st == 'old':
            self.old.append(d)
        elif st == 'note':
            self.notes.append(d)
        else:
            self.kept.append(html.escape(d, quote=False))


def body(h):
    h = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->|<head\b.*?</head>', '', h)
    i = h.lower().find('<body')
    return h[h.index('>', i) + 1:] if i >= 0 else h


NOTE_LINE = re.compile(r'^-\s*(?:Reda|Acresc|Revog|Vide|Renumer|Supr|Alter|Inclu|Declar|Suspen|Regulam|Ver\b|Veja|'
                       r'Efic|ADI|Express|Texto|Vig|Prorrog|Nova|Com |Promulg|Retific|Republic|Derrog|Transform|'
                       r'Modific|Ac[óo]rd|Decis|Liminar|Mantid|Restab|Repristin|Obs|Nota)', re.I)


def split(h):
    p = Split()
    p.feed(body(h))
    p.close()
    kept = ''.join(p.kept)
    notes = [norm(n) for n in ''.join(p.notes).split('\n') if norm(n)]
    lines = []
    for kind, l in lines_of(kept):
        if re.match(r'(?i)Este texto n[ãa]o substitui o publicad', l):
            continue  # the publisher's notice, not text
        if NOTE_LINE.match(l):
            notes.append(l)  # a note the page did not put in its note font
            continue
        lines.append((kind, l))
    return lines, notes, ''.join(p.old)


DMY = re.compile(r'\b(\d{1,2})[º°]?[-/.](\d{1,2})[-/.](\d{4})\b')
MONTHS = {m: i + 1 for i, m in enumerate(['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
                                           'setembro', 'outubro', 'novembro', 'dezembro'])}
LONG = re.compile(r'\b(\d{1,2})[º°o]?\s+de\s+(' + '|'.join(MONTHS) + r')\s+de\s+(\d{4})', re.I)


def dates(s):
    out = [f'{int(y):04d}-{int(mo):02d}-{int(d):02d}' for d, mo, y in DMY.findall(s) if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31]
    out += [f'{int(y):04d}-{MONTHS[mo.lower()]:02d}-{int(d):02d}' for d, mo, y in LONG.findall(s)]
    return out


def is_alteration(n):
    return not re.match(r'^-?\s*(Vide|Ver\b|Veja|Regulamentad|Obs|Nota)', n, re.I)


COUNTRY = {
    'code': 'BR-GO', 'name': 'Goiás', 'slug': 'brazil-goias', 'lang': 'pt', 'tz': 'America/Sao_Paulo',
    'future_branch': 'futuro',
    'publisher': {'name': 'Secretaria de Estado da Casa Civil de Goiás (Legisla Goiás)',
                  'email': 'legisla@casacivil.go.gov.br.invalid'},
    'default_in_force_rule': {
        'text': 'Decreto-Lei 4.657/1942 (LINDB) art. 1: unless it says otherwise, a law takes effect 45 days after its '
                'official publication. Goiás laws almost always say "Esta Lei entra em vigor na data de sua '
                'publicação"; this record dates each act as enacted by its publication in the Diário Oficial do Estado '
                '(the Constituição by its promulgation).',
        'source': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm'},
    'licence_note': 'Texts: Legisla Goiás, Secretaria de Estado da Casa Civil de Goiás, legisla.casacivil.go.gov.br. '
                    'Lei 9.610/1998 art. 8 IV: the texts of laws and other official acts are not protected by '
                    'copyright. Non-official text: only the Diário Oficial do Estado is authoritative.',
}
DECISIONS = [
    'An act the Casa Civil shows no alteration note for is given as enacted, credited to the act itself and dated by its '
    'publication in the Diário Oficial do Estado (the Constituição by its promulgation, 5 October 1989). An altered '
    'act is given only as its text in force, credited to the publisher as the oldest version available and dated by the '
    'latest date its alteration notes cite. The wordings in between are not reconstructed yet, so no earlier version '
    'is given rather than a wrong one.',
    'The text in force leaves out the earlier wordings the compiled text shows struck through or in red (each followed '
    'by a note such as "- Redação original") and the publisher\'s notes (in Arial Black, such as "- Redação dada pela '
    'Emenda Constitucional nº 46, de 9-9-2010, D.O. de 7-12-2010", the green "Vide" notes and the <nota> elements of '
    'newer pages). "Vide" notes do not date a version. The notice "Este texto não substitui o publicado no D.O. de ..." '
    'is left out. In an act with no alteration note, what is struck through is the act\'s own rendering of what it '
    'deletes from the law it amends (in its quoted annexes and tables) and is left out; such an act is given as '
    'enacted. An altered act whose notes cite no date is left out.',
    'One file per Art. (articles of the Ato das Disposições Constitucionais Transitórias as adt-*); headings of the '
    'Títulos, Capítulos and Seções stand above the first article under them; "000-titulo" holds the title, the ementa '
    'and the preamble. Text after the last article (place, date, signatures) stays with the last article.',
    'Tables are one line per row, cells separated by " | "; images are left out.',
]
AI = ["Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is used as legal "
      "text or dates: every word comes from the Legisla Goiás records."]


def raw(url):
    p = CACHE / 'raw' / sha(url.encode())
    return p.read_bytes() if p.exists() else None


def act_of(url, kind):
    b = raw(url)
    if b is None:
        return None, {}, 'not fetched'
    r = json.loads(b)
    h = r.get('conteudo') or ''
    if not h.strip():
        return None, {}, 'no text'
    lines, notes, old = split(h)
    enacted = r.get('data_legislacao')
    dos = sorted(d['data'] for d in r.get('diarios_estaduais') or [] if d.get('data') and not d.get('errata'))
    published = dos[0] if dos else None
    page = f"{SITE}/{r['id']}"
    if kind == 'con':
        slug, law_key, short, title = 'constituicao', 'constituicao-1989', 'CE-GO', 'Constituição do Estado de Goiás'
        first = enacted
        label = title
    else:
        n = int(re.sub(r'\D', '', r.get('numero') or '0') or 0)
        y = str(r['ano'])
        slug = law_key = f'lc-{y}-{n:03d}'
        short, label = f'LC {n}/{y}', f'Lei Complementar nº {n}, de {y}'
        first = published or enacted
        title = label
    if not first:
        return None, {}, 'no date'
    ementa = norm(r.get('ementa') or '')
    laws = {law_key: {'label': label, 'title': ementa or label, 'kind': 'law', 'enacted': enacted, 'published': published,
                      'url': page, 'temporary_until': None, 'restores': None, 'note': None}}
    alts = [n for n in notes if is_alteration(n)]
    alter = sorted(d for n in alts for d in dates(n) if d > first)
    units = units_of(lines, adt=(kind == 'con'))
    if not units:
        return None, {}, 'no text'
    if alts and not alter:
        return None, {}, 'altered, no dated note'
    # Without any alteration note, struck text is the act's own rendering of what it deletes from the law it amends
    # (in its quoted annexes and tables); the red "Este texto não substitui o publicado no D.O." notice is not text.
    v = {'from': alter[-1] if alter else first, 'source_url': url, 'sha256': sha(b), 'units': units}
    if alter:
        v['note'] = (f'Text in force as compiled by the Casa Civil de Goiás; {label} was altered on {len(set(alter))} '
                     f'date(s) its notes cite, the latest {alter[-1]}.')
    act = {'slug': slug, 'short': short,
           'title': title + (f' ({ementa})' if ementa and len(ementa) < 160 and kind != 'con' else ''),
           'url': page, 'first_law': None if alter else law_key, 'earlier_laws': [law_key] if alter else [],
           'versions': [v]}
    return act, laws, 'ok'


def part(name, acts, laws, today):
    c = {'country': COUNTRY,
         'sources': [{'name': 'Legisla Goiás (Secretaria de Estado da Casa Civil de Goiás): the record of each act',
                      'url': 'https://legisla.casacivil.go.gov.br', 'retrieved': today,
                      'licence': COUNTRY['licence_note'], 'notes': f'{len(acts)} acts in this part.'}],
         'laws': laws, 'acts': acts, 'applies': [], 'decisions': DECISIONS, 'ai_use': AI}
    return write_part(HERE / 'corpus.d', name, c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--part-size', type=int, default=50)
    a = ap.parse_args()
    if a.only in ('', 'constituicao'):
        act, laws, why = act_of(f'{API}/constituicao_estadual', 'con')
        print('constituicao', why)
        if act:
            print(part('10-constituicao', [act], laws, a.today))
    if a.only in ('', 'lc'):
        idx_p = CACHE / 'lc-index.json'
        if not idx_p.exists():
            return
        idx = json.loads(idx_p.read_text(encoding='utf-8'))
        lcs = sorted(idx['acts'], key=lambda r: (str(r.get('data_legislacao') or r['ano']), r['id']))
        for i in range(0, len(lcs), a.part_size):
            chunk = lcs[i:i + a.part_size]
            if any(raw(f"{API}/{r['id']}") is None for r in chunk):
                continue  # a part is written only once every act in it is fetched, so a published part never changes
            acts, laws, why = [], {}, {}
            for r in chunk:
                act, l, w = act_of(f"{API}/{r['id']}", 'lc')
                why[w] = why.get(w, 0) + 1
                if act:
                    acts.append(act); laws.update(l)
            print(part(f'20-lc-{i // a.part_size + 1:02d}', acts, laws, a.today), why)


if __name__ == '__main__':
    main()
